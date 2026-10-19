import csv
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from bankdetails.models import BankDetail
from contact.models import Contact
from delaer.models import DealerProfile, SalesExecutive
from products.models import Product
from products.views import is_live

from .forms import OrderItemForm
from .models import Order, OrderItem

# Create your views here.


class _NotEnoughStock(Exception):
    """Raised inside the finalise transaction so it rolls back cleanly."""


def _same_state(company, dealer):
    """Is this an intra-state sale? Same state -> CGST + SGST, otherwise IGST.

    The state field decides. Only when one side has no state set do we fall
    back to the GSTIN, whose first two digits are the state code.
    """
    if company is None or dealer is None:
        return True          # nothing to compare — treat as local

    ours = (getattr(company, "state", "") or "").strip().lower()
    theirs = (dealer.state or "").strip().lower()
    if ours and theirs:
        return ours == theirs

    if getattr(company, "gstin", "") and dealer.gstin:
        return company.gstin[:2] == dealer.gstin[:2]

    return False             # not enough information — bill as inter-state


def _company():
    """Us — the head office contact, which is the invoice letterhead."""
    return Contact.objects.filter(is_primary=True).first() or Contact.objects.first()


def _tax_context(order):
    """How this order's GST splits, for the order page and the invoice alike.

    Kept in one place so the figures a dealer reads on screen are the same
    ones that come out of the printer.
    """
    dealer = order.dealer
    # Same state as us -> the tax splits into CGST + SGST; a different state
    # is an inter-state sale and carries IGST instead.
    same_state = _same_state(_company(), dealer)

    gst = order.total_gst
    cgst, sgst = order._halve(gst)

    return {
        "same_state": same_state,
        "cgst": cgst,
        "sgst": sgst,      # the odd paisa lands here, never lost
        "igst": gst,
        "tax_rows": order.gst_breakup,
    }


def _dealer(request):
    """The signed-in user's dealer profile, or None if they haven't made one."""
    return DealerProfile.objects.filter(user=request.user).first()


def is_manager(user):
    """Staff, superusers and anyone in the Management group see every dealer's
    orders. Everyone else sees only their own."""
    return (
        user.is_superuser
        or user.is_staff
        or user.groups.filter(name="Management").exists()
    )


def _sales(request):
    """The signed-in user's sales executive profile, or None.

    Having the profile is what makes a login a salesman — there is no group
    to keep in step with it, and only the admin can create one. An executive
    switched off keeps their past orders but stops being treated as one.
    """
    user = request.user
    if not user.is_authenticated:
        return None
    return SalesExecutive.objects.filter(user=user, is_active=True).first()


def is_sales(user):
    """For templates and other apps that only need the yes/no."""
    return (
        user.is_authenticated
        and SalesExecutive.objects.filter(user=user, is_active=True).exists()
    )


def _own_orders(request):
    """Orders this user may change, as opposed to merely see.

    A dealer's own orders, and the orders a salesman raised — both can work
    on them. Management is deliberately not here: a manager may look at any
    order but places none, which is the rule the page has always followed.
    """
    mine = Q(pk__in=[])

    sales = _sales(request)
    if sales:
        mine |= Q(sales_executive=sales)

    dealer = _dealer(request)
    if dealer:
        mine |= Q(dealer=dealer)

    return Order.objects.filter(mine).prefetch_related("items__product")


# a salesman serves many dealers, so the one they are working for is kept in
# the session between requests rather than threaded through every URL
SALES_DEALER_KEY = "sales_dealer"


def _acting_dealer(request):
    """The dealer an order is being raised for.

    A dealer ordering for themselves needs no choice — it is them, always.
    A salesman picks, and the choice sticks until they change it. Anyone who
    is both is treated as a dealer buying for themselves, because that is the
    account they signed in with.
    """
    own = _dealer(request)
    if own:
        return own

    if _sales(request):
        chosen = request.session.get(SALES_DEALER_KEY)
        if chosen:
            return DealerProfile.objects.filter(pk=chosen).first()

    return None


def _visible_orders(request):
    """What this user is allowed to see — read-only access.

    Three kinds of login, in order of reach:

    * management sees every order;
    * a sales executive sees the orders raised in their name, whichever
      dealer they were for;
    * a dealer sees their own orders, however they were raised.

    A login can be both — a salesman who also buys — so the two are OR'd
    rather than ranked. Anyone who is neither sees nothing, which is what a
    fresh account with no profile gets.

    Every other module reads visibility through this one function, so the
    reports and the payment page follow the same rule without repeating it.
    """
    orders = (
        Order.objects
        .select_related("dealer", "sales_executive")
        .prefetch_related("items__product")
    )

    if is_manager(request.user):
        return orders

    mine = Q(pk__in=[])          # matches nothing until a profile says otherwise

    sales = _sales(request)
    if sales:
        mine |= Q(sales_executive=sales)

    dealer = _dealer(request)
    if dealer:
        mine |= Q(dealer=dealer)

    return orders.filter(mine)


# How many order rows a page shows. The product list and the reports use the
# same number, so every long table in the project agrees.
PER_PAGE = 100


def _filtered_orders(request):
    """Visible orders narrowed by the status, dealer and date filters.

    The list page and the export both call this, so a download always matches
    what is on screen.
    """
    orders = _visible_orders(request)

    status = request.GET.get("status")
    if status in Order.Status.values:
        orders = orders.filter(status=status)

    # managers can narrow to one dealer
    dealer_id = request.GET.get("dealer")
    if is_manager(request.user) and dealer_id and dealer_id.isdigit():
        orders = orders.filter(dealer_id=dealer_id)

    # managers can narrow to one salesman, or to the orders with none
    sales_id = request.GET.get("sales")
    if is_manager(request.user) and sales_id:
        if sales_id == "direct":
            orders = orders.filter(sales_executive__isnull=True)
        elif sales_id.isdigit():
            orders = orders.filter(sales_executive_id=sales_id)

    # date range — either end may be left empty
    date_from = parse_date(request.GET.get("from", "") or "")
    date_to = parse_date(request.GET.get("to", "") or "")
    if date_from:
        orders = orders.filter(ordered_on__gte=date_from)
    if date_to:
        orders = orders.filter(ordered_on__lte=date_to)

    return orders


def _open_draft(dealer, sales=None):
    """The cart: one open draft per dealer per person raising it.

    Keyed on the salesman as well as the dealer, so two people working for
    the same dealer at once each have their own basket — and a salesman's
    draft never merges into the dealer's own.
    """
    order = (
        Order.objects
        .filter(dealer=dealer, status=Order.Status.DRAFT, sales_executive=sales)
        .prefetch_related("items__product")
        .first()
    )
    return order or Order.objects.create(dealer=dealer, sales_executive=sales)


def _open_draft_if_any(dealer, sales=None):
    """The same basket, but without creating one. The shop shows the cart
    only when there is something in it, and browsing should not leave empty
    drafts behind."""
    return (
        Order.objects
        .filter(dealer=dealer, status=Order.Status.DRAFT, sales_executive=sales)
        .prefetch_related("items__product")
        .first()
    )


def _add_line(order, product, qty):
    """Add to the order, or bump the quantity if the product is already on it.

    Returns an error message and writes nothing when the combined quantity
    would go past stock; returns None once the line is saved.

    The combined figure is the whole point. Checking only the quantity being
    added lets someone add 3, then 3 again, to a product with 5 on the shelf
    — each add is fine on its own and the line ends up at 6.
    """
    line = order.items.filter(product=product).first()
    already = line.qty if line else 0
    wanted = already + qty

    if wanted > product.stock:
        if already:
            return (
                f"{product.name}: only {product.stock} in stock and "
                f"{already} already on this order."
            )
        return f"{product.name}: only {product.stock} in stock."

    if line:
        line.qty = wanted
        line.save()
    else:
        OrderItem.objects.create(order=order, product=product, qty=qty)
    return None


@login_required
def myorder(request):
    """Order records — the dealer's own, or every dealer's for a manager."""
    dealer = _dealer(request)
    manager = is_manager(request.user)
    sales = _sales(request)

    # a manager has no orders of their own, and a salesman's are held under
    # their name rather than a dealer profile — neither needs one setting up
    if dealer is None and not manager and not sales:
        messages.error(request, "Set up your dealer profile before placing orders.")
        return redirect("delaer:mydealer")

    orders = list(_filtered_orders(request))
    status = request.GET.get("status")
    dealer_id = request.GET.get("dealer")

    # Totals across whatever the filter left on screen. Summed from the
    # orders' own properties — each line is already rounded there, so these
    # agree with the figures in the rows above them to the paisa.
    totals = {
        "count": len(orders),
        "qty": sum(o.total_qty for o in orders),
        "net": sum((o.total_net for o in orders), Decimal("0.00")),
        "gst": sum((o.total_gst for o in orders), Decimal("0.00")),
        "amount": sum((o.total_amount for o in orders), Decimal("0.00")),
    }

    # the status links carry the dealer and date range along, so switching
    # status does not silently reset the other filters. The page number is
    # dropped: a different status is a different list, and page 7 of it may
    # not exist.
    keep = request.GET.copy()
    keep.pop("status", None)
    keep.pop("page", None)
    keep = keep.urlencode()

    # 100 rows a page, the same size and the same ?per_page=all escape hatch the
    # product list offers. Paginated after the totals above, so the footer keeps
    # describing the whole filtered list rather than the hundred rows on screen.
    # The export runs _filtered_orders() again for itself, so it is unaffected.
    show_all = request.GET.get("per_page") == "all"
    paginator = Paginator(orders, len(orders) or 1 if show_all else PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    # the page links must carry the filter, or page 2 would be unfiltered
    params = request.GET.copy()
    params.pop("page", None)

    # the 100-per-page / Show all links keep the filter but set per_page
    # themselves, so it is dropped here
    base = request.GET.copy()
    base.pop("page", None)
    base.pop("per_page", None)

    return render(request, "orders/myorder.html", {
        "orders": page.object_list,
        "page": page,
        "page_range": paginator.get_elided_page_range(
            page.number, on_each_side=1, on_ends=1),
        "querystring": params.urlencode(),
        "base_query": base.urlencode(),
        "show_all": show_all,
        "totals": totals,
        "status": status or "all",
        "dealer": dealer,
        "is_manager": manager,
        "dealers": DealerProfile.objects.all() if manager else None,
        "dealer_id": dealer_id or "",
        "sales": sales,
        "sales_people": SalesExecutive.objects.all() if manager else None,
        "sales_id": request.GET.get("sales", ""),
        "date_from": request.GET.get("from", ""),
        "date_to": request.GET.get("to", ""),
        "keep": keep,
        # the export links reuse the full filter, status included
        "query": request.GET.urlencode(),
    })


def _no_dealer(request):
    """Where to send someone who cannot raise an order yet, and why.

    A salesman who has not picked a dealer is sent back to the shop to
    choose one; anyone with no profile at all is sent to set one up.
    """
    if _sales(request):
        messages.error(request, "Choose the dealer this order is for first.")
        return redirect("myorder:catalogue")

    messages.error(request, "Set up your dealer profile before placing orders.")
    return redirect("delaer:mydealer")


@login_required
def cart(request):
    """The open draft order — created on first visit."""
    dealer = _acting_dealer(request)
    if dealer is None:
        return _no_dealer(request)

    return redirect("myorder:edit", pk=_open_draft(dealer, _sales(request)).pk)


@login_required
def catalogue(request):
    """Every product as a card. The button adds it straight to the cart.

    A salesman chooses which dealer they are buying for; a dealer is simply
    themselves. Picking a dealer is a POST so it is not repeated on refresh.
    """
    sales = _sales(request)

    if request.method == "POST" and sales and "dealer" in request.POST:
        wanted = request.POST.get("dealer", "")
        if wanted.isdigit() and DealerProfile.objects.filter(pk=wanted).exists():
            request.session[SALES_DEALER_KEY] = int(wanted)
        else:
            request.session.pop(SALES_DEALER_KEY, None)
        return redirect("myorder:catalogue")

    dealer = _acting_dealer(request)

    # a salesman with nobody chosen yet still gets the page — it shows the
    # dealer picker and nothing else, rather than bouncing them somewhere
    if dealer is None and not sales:
        return _no_dealer(request)

    draft = (
        _open_draft_if_any(dealer, sales) if dealer else None
    )

    # same search and stock filter as the products table, run in the database
    search = request.GET.get("q", "").strip()
    status = request.GET.get("status", "all")
    products = (
        Product.objects.select_related("brand", "unit")
        .search(search)
        .in_stock_state(status)
    )

    context = {
        "products": products,
        "draft": draft,
        "search": search,
        "status": status,
        # a salesman sees who they are buying for, and can change it
        "sales": sales,
        "acting_dealer": dealer,
        "dealers": DealerProfile.objects.all() if sales else None,
    }

    # typing in the search box asks for the cards only, so the shop filters
    # itself without a reload; without JS this still returns the full page
    if is_live(request):
        return render(request, "orders/_shop_results.html", context)

    return render(request, "orders/catalogue.html", context)


def _cart_json(order):
    """What the shop page needs to redraw its cart table."""
    return {
        "order_no": order.order_no,
        "url": reverse("myorder:edit", args=[order.pk]),
        "qty": order.total_qty,
        "total": f"{order.total_amount}",
        "items": [
            {"name": i.product.name, "qty": i.qty, "total": f"{i.line_total}"}
            for i in order.items.all()
        ],
    }


@login_required
def add_to_cart(request, product_pk):
    """One card's Add button. Straight into the open draft order.

    Answers with JSON when the page asks for it (the shop uses fetch, so it
    never reloads) and falls back to a redirect for a plain form post."""
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    sales = _sales(request)
    dealer = _acting_dealer(request)

    if dealer is None:
        trouble = ("Choose the dealer this order is for first." if sales
                   else "Set up your dealer profile first.")
        if wants_json:
            return JsonResponse({"ok": False, "error": trouble}, status=400)
        return _no_dealer(request)

    error = None
    if request.method == "POST":
        product = get_object_or_404(Product, pk=product_pk)
        try:
            qty = int(request.POST.get("qty", 1))
        except ValueError:
            qty = 1

        if product.stock < 1:
            error = f"{product.name} is out of stock."
        elif qty < 1:
            error = "Enter a quantity of at least 1."
        else:
            order = _open_draft(dealer, sales)
            # _add_line weighs the quantity against what the cart already
            # holds for this product, not just against the amount being added
            error = _add_line(order, product, qty)

            if error is None:
                if wants_json:
                    # _open_draft prefetched the items, so this instance still holds
                    # the pre-update cache — read it back before reporting totals
                    order = Order.objects.prefetch_related("items__product").get(pk=order.pk)
                    return JsonResponse({
                        "ok": True,
                        "message": f"{qty} x {product.name} added.",
                        "cart": _cart_json(order),
                    })
                messages.success(request, f"{qty} x {product.name} added to your cart.")

    if wants_json:
        return JsonResponse({"ok": False, "error": error or "Nothing to add."}, status=400)
    if error:
        messages.error(request, error)
    return redirect("myorder:catalogue")


@login_required
def edit(request, pk):
    """Add lines to a draft order. A manager may open another dealer's order,
    but read-only — only the owner can change it."""
    order = get_object_or_404(_visible_orders(request), pk=pk)

    # the dealer it is for, or the salesman who raised it, may work on it;
    # a manager may look but not change
    mine = _own_orders(request).filter(pk=order.pk).exists()
    can_edit = mine and order.is_draft

    if request.method == "POST" and can_edit:
        form = OrderItemForm(request.POST, order=order)
        if form.is_valid():
            product = form.cleaned_data["product"]
            # the form already checked stock; _add_line checks again because
            # it is the only place that writes a line, whoever calls it
            error = _add_line(order, product, form.cleaned_data["qty"])
            if error:
                messages.error(request, error)
            else:
                messages.success(request, f"{product.name} added.")
            return redirect("myorder:edit", pk=order.pk)
    else:
        form = OrderItemForm(order=order)

    return render(request, "orders/order_edit.html", {
        "order": order,
        "form": form,
        "can_edit": can_edit,
        "mine": mine,
        # the same GST split the invoice prints, so there are no surprises
        # between placing the order and printing it
        **_tax_context(order),
    })


@login_required
def hold(request, pk):
    """Park this order so a new one can be started, and come back to it later."""
    order = get_object_or_404(_own_orders(request), pk=pk)

    if request.method == "POST" and order.is_draft:
        if not order.items.exists():
            messages.error(request, "Nothing to hold — the order is empty.")
            return redirect("myorder:edit", pk=order.pk)

        order.status = Order.Status.HOLD
        order.save()
        messages.success(request, f"Order {order.order_no} is on hold.")
        return redirect("myorder:myorder")

    return redirect("myorder:edit", pk=order.pk)


@login_required
def resume(request, pk):
    """Pick a held order back up. Any order already open is held first, so a
    dealer never ends up with two live drafts."""
    order = get_object_or_404(_own_orders(request), pk=pk)

    if request.method == "POST" and order.is_hold:
        if not order.can_resume:
            messages.error(
                request,
                f"Order {order.order_no} is from {order.ordered_on:%d %b %Y} "
                "and can only be continued on the same date.",
            )
            return redirect("myorder:myorder")

        open_draft = (
            _own_orders(request)
            .filter(status=Order.Status.DRAFT)
            .exclude(pk=order.pk)
            .first()
        )
        if open_draft:
            open_draft.status = Order.Status.HOLD
            open_draft.save()
            messages.info(request, f"Order {open_draft.order_no} was put on hold.")

        order.status = Order.Status.DRAFT
        order.save()
        messages.success(request, f"Continuing order {order.order_no}.")

    return redirect("myorder:edit", pk=order.pk)


@login_required
def remove_item(request, pk, item_pk):
    order = get_object_or_404(_own_orders(request), pk=pk)
    if request.method == "POST" and order.is_draft:
        get_object_or_404(order.items, pk=item_pk).delete()
        messages.success(request, "Line removed.")
    return redirect("myorder:edit", pk=order.pk)


@login_required
def finalise(request, pk):
    """Draft -> Final, and take the ordered quantities out of stock.

    Stock moves here rather than when a line is added to the cart: a draft is
    still being edited and reserving against it would hide stock that nobody
    has actually committed to buying.
    """
    order = get_object_or_404(_own_orders(request), pk=pk)

    if request.method == "POST" and order.is_draft:
        if not order.items.exists():
            messages.error(request, "Add at least one item before placing the order.")
            return redirect("myorder:edit", pk=order.pk)

        try:
            with transaction.atomic():
                # lock the products so two dealers placing orders at the same
                # moment cannot both pass the stock check below
                lines = list(order.items.select_related("product").select_for_update(of=("product",)))

                short = [
                    f"{line.product.name} (want {line.qty}, have {line.product.stock})"
                    for line in lines
                    if line.qty > line.product.stock
                ]
                if short:
                    raise _NotEnoughStock("; ".join(short))

                for line in lines:
                    # F() so the subtraction happens in the database, never
                    # from a value this request read a moment ago
                    Product.objects.filter(pk=line.product_id).update(
                        stock=F("stock") - line.qty
                    )

                order.status = Order.Status.FINAL
                order.save()
        except _NotEnoughStock as exc:
            messages.error(request, f"Not enough stock: {exc}")
        else:
            messages.success(request, f"Order {order.order_no} placed. Stock updated.")

    return redirect("myorder:edit", pk=order.pk)


# ---------------------------------------------------------------- exports

ORDER_COLUMNS = ["Order No", "Dealer", "Date", "Items", "Qty", "Net", "GST", "Total", "Status"]


def _order_rows(orders):
    for o in orders:
        yield [
            o.order_no, o.dealer.name, o.ordered_on.strftime("%d-%m-%Y"),
            o.items.count(), o.total_qty,
            f"{o.total_net}", f"{o.total_gst}", f"{o.total_amount}",
            o.get_status_display(),
        ]


@login_required
def export_orders(request, fmt):
    """Download the order list as CSV, Excel or PDF — filters included."""
    orders = _filtered_orders(request)
    stamp = timezone.localdate().isoformat()
    filename = f"orders-{stamp}"

    if fmt == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        writer = csv.writer(response)
        writer.writerow(ORDER_COLUMNS)
        writer.writerows(_order_rows(orders))
        return response

    if fmt == "excel":
        from openpyxl import Workbook
        from openpyxl.styles import Font

        book = Workbook()
        sheet = book.active
        sheet.title = "Orders"
        sheet.append(ORDER_COLUMNS)
        for cell in sheet[1]:
            cell.font = Font(bold=True)

        rows = list(_order_rows(orders))
        for row in rows:
            sheet.append(row)
        for i, name in enumerate(ORDER_COLUMNS, start=1):
            longest = max([len(name)] + [len(str(r[i - 1])) for r in rows] or [0])
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
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
            title=f"Orders {stamp}",
        )
        styles = getSampleStyleSheet()
        data = [ORDER_COLUMNS] + [[str(v) for v in row] for row in _order_rows(orders)]

        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4e89")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (3, 1), (-2, -1), "RIGHT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        doc.build([Paragraph(f"Orders — {stamp}", styles["Heading2"]), Spacer(1, 6), table])

        response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}.pdf"'
        return response

    raise Http404("Unknown export format.")


@login_required
def print_order(request, pk):
    """Printable copy. A manager can print any dealer's order."""
    order = get_object_or_404(_visible_orders(request), pk=pk)

    # our own company is the letterhead (from the Contact app — head office
    # first); the order's dealer is who it is billed to
    bank = BankDetail.objects.filter(is_primary=True).first() or BankDetail.objects.first()

    # invoice rounding: the payable figure goes to the nearest rupee, and the
    # difference is shown as its own line so the totals still add up
    gross = order.total_amount
    payable = gross.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    return render(request, "orders/order_print.html", {
        "order": order,
        "company": _company(),
        "dealer": order.dealer,
        "bank": bank,
        "round_off": payable - gross,
        "payable": payable,
        **_tax_context(order),
    })
