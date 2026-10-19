import csv
import os
from io import BytesIO
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import ProductForm
from .models import Product

# Create your views here.


def is_live(request):
    """Did the page ask for just the results, rather than the whole page?

    The search box and the filter links send this header through fetch, so
    the browser swaps the rows in place instead of reloading. Same header
    the shop's Add button already uses.
    """
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def products(request):
    """Product list. The Add Product modal posts back to this same URL."""
    if request.method == "POST":
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"{product.name} was added.")
            # redirect after POST so a refresh doesn't re-submit the form
            return redirect("products:products")
        # invalid — fall through and re-render so the modal can reopen
        # with the user's input and the error messages still in place
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProductForm()

    # brand and unit are shown per row — pull them in the same query
    products = Product.objects.select_related("brand", "unit")

    # Search and the stock filter run in the database, not in the browser.
    # With pagination a client-side filter would only ever see the current
    # page, so "Low" would hide rows instead of finding all of them.
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    products = products.search(search).in_stock_state(status)

    # 100 a page by default; ?per_page=all puts everything on one page
    per_page = request.GET.get("per_page", "100")
    show_all = per_page == "all"
    paginator = Paginator(products, products.count() or 1 if show_all else 100)
    page = paginator.get_page(request.GET.get("page"))

    # "1 2 … 5 6 7 … 20" — built here because the template cannot pass the
    # current page number to get_elided_page_range()
    page_range = paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)

    # keeps q/status on the page links, so paging never drops the filter
    params = request.GET.copy()
    params.pop("page", None)

    # the All / 100-per-page links need q and status but not per_page
    base = request.GET.copy()
    base.pop("page", None)
    base.pop("per_page", None)

    context = {
        "form": form,
        "page": page,
        "page_range": page_range,
        "products": page.object_list,
        "search": search,
        "status": status,
        "show_all": show_all,
        "querystring": params.urlencode(),
        "base_query": base.urlencode(),
    }

    # typing in the search box asks for the results only, so the page does
    # not reload; without JS the same view returns the full page as before
    if is_live(request):
        return render(request, "products/_product_results.html", context)

    return render(request, "products/product.html", context)


def detail(request, pk):
    """Full details for one product. Linked to from the product list, the
    shop cards, and anywhere else a product is shown."""
    product = get_object_or_404(Product.objects.select_related("brand", "unit"), pk=pk)
    return render(request, "products/product_detail.html", {"product": product})


# how many suggestions the topbar drop-down shows before saying "see all"
SUGGEST_LIMIT = 8


def suggest(request):
    """JSON for the search box in the topbar — every page has one.

    Answers as you type, so nothing here renders a template or touches the
    session: it is one indexed query and a short list.
    """
    term = request.GET.get("q", "").strip()
    if len(term) < 2:
        # a single letter matches almost everything and helps nobody
        return JsonResponse({"results": [], "total": 0, "url": ""})

    matches = Product.objects.select_related("brand", "unit").search(term)
    total = matches.count()

    results = [
        {
            "name": p.name,
            "partno": p.partno,
            "brand": str(p.brand),
            "price": f"{p.price_including_gst}",
            "unit": str(p.unit),
            "image": p.front_url,
            "label": p.stock_label,
            "badge": p.stock_badge,
            "url": reverse("products:detail", args=[p.pk]),
        }
        for p in matches[:SUGGEST_LIMIT]
    ]

    return JsonResponse({
        "results": results,
        "total": total,
        # "see all N" goes to the full list, already filtered by this term
        "url": f"{reverse('products:products')}?q={quote(term)}",
    })


# ---------------------------------------------------------------- exports

EXPORT_COLUMNS = [
    "Name", "Part No", "Brand", "Unit", "HSN", "GST %",
    "Price", "Net", "Gross", "Stock", "Status",
]

THUMB_PX = 56          # how big the embedded picture is, in pixels
PLACEHOLDER = settings.BASE_DIR / "static" / "assets" / "imgs" / "product-placeholder.png"


def _export_products():
    return Product.objects.select_related("brand", "unit")


def _export_row(p):
    """One list per product, in the same order as EXPORT_COLUMNS."""
    return [
        p.name, p.partno, str(p.brand), str(p.unit), p.hsn, f"{p.gst}",
        f"{p.price}", f"{p.price_excluding_gst}", f"{p.price_including_gst}",
        p.stock, p.stock_label,
    ]


def _thumbnail(product):
    """A small PNG of the product's front image as a BytesIO, or None.

    Downscaled here so a few hundred full-size photos can't turn the export
    into a 200 MB file — the sheet only ever shows them thumbnail-sized.
    """
    from PIL import Image as PILImage

    try:
        source = product.image_front.path if product.image_front else PLACEHOLDER
        if not os.path.exists(source):
            return None
        image = PILImage.open(source)
        image.thumbnail((THUMB_PX * 2, THUMB_PX * 2))   # 2x for a crisp print
        if image.mode not in ("RGB", "RGBA"):
            image = image.convert("RGB")
        buffer = BytesIO()
        image.save(buffer, "PNG")
        buffer.seek(0)
        return buffer
    except (OSError, ValueError):
        # an unreadable or missing file must not break the whole export
        return None


def export(request, fmt):
    """Download the product list as CSV, Excel or PDF."""
    stamp = timezone.localdate().isoformat()
    filename = f"products-{stamp}"

    if fmt == "csv":
        # a spreadsheet cell can't hold a picture, so give the link instead
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(response)
        writer.writerow(EXPORT_COLUMNS + ["Image URL"])
        for p in _export_products():
            writer.writerow(_export_row(p) + [request.build_absolute_uri(p.front_url)])
        return response

    if fmt == "excel":
        from openpyxl import Workbook
        from openpyxl.styles import Font

        from openpyxl.drawing.image import Image as XLImage

        book = Workbook()
        sheet = book.active
        sheet.title = "Products"

        # picture first, then the text columns
        sheet.append(["Image"] + EXPORT_COLUMNS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        rows = []
        for p in _export_products():
            row = _export_row(p)
            rows.append(row)
            sheet.append([""] + row)               # column A left free for the picture
            line = sheet.max_row
            sheet.row_dimensions[line].height = THUMB_PX * 0.78   # points, not pixels

            thumb = _thumbnail(p)
            if thumb:
                picture = XLImage(thumb)
                picture.width = picture.height = THUMB_PX
                sheet.add_image(picture, f"A{line}")

        sheet.column_dimensions["A"].width = THUMB_PX / 6.5
        # rough auto-width from the longest value in each column
        for i, name in enumerate(EXPORT_COLUMNS, start=2):
            longest = max([len(name)] + [len(str(r[i - 2])) for r in rows] or [0])
            sheet.column_dimensions[sheet.cell(row=1, column=i).column_letter].width = min(longest + 2, 40)
        sheet.freeze_panes = "A2"

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        book.save(response)
        return response

    if fmt == "pdf":
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
        )

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
            title=f"Products {stamp}",
        )
        styles = getSampleStyleSheet()

        data = [["Image"] + EXPORT_COLUMNS]
        for p in _export_products():
            thumb = _thumbnail(p)
            cell = RLImage(thumb, width=THUMB_PX * 0.62, height=THUMB_PX * 0.62) if thumb else ""
            data.append([cell] + [str(v) for v in _export_row(p)])

        table = Table(data, repeatRows=1, colWidths=[THUMB_PX * 0.72] + [None] * len(EXPORT_COLUMNS))
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 1), (0, -1), "CENTER"),
            ("ALIGN", (6, 1), (-2, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))

        doc.build([
            Paragraph(f"Products — {stamp}", styles["Heading2"]),
            Spacer(1, 6),
            table,
        ])

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response

    raise Http404("Unknown export format.")
