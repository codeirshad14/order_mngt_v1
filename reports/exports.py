"""Downloading a report as CSV, Excel or PDF.

The rows are never rebuilt here. The export view calls the report's own view,
which returns a TemplateResponse, and reads the context that page was about to
render. So a download is the report on screen — same filters, same order, same
figures — and the two can never drift apart.

Each report contributes one function that flattens its context into a header
row and a list of text rows. That is the only report-specific code below; the
three writers are shared.
"""

import csv
from io import BytesIO

from django.http import Http404, HttpResponse
from django.utils import timezone

# how wide a column may grow in the spreadsheet before it stops auto-sizing
MAX_COL_WIDTH = 42


def _text(value):
    """One cell, as text. None becomes an empty cell, not the word 'None'."""
    if value is None:
        return ""
    return str(value)


# --------------------------------------------------------- per report rows
#
# Each builder takes the page's own context and returns (columns, rows).
# The Dealer column only appears for a manager: a dealer's own export would
# just repeat their name down the page.


def _order_book(ctx):
    manager = ctx["is_manager"]
    columns = ["Order No"] + (["Dealer"] if manager else []) + [
        "Date", "Raised By", "Items", "Net", "GST", "Total", "Status",
    ]
    rows = []
    for order in ctx["orders"]:
        rows.append(
            [order.order_no]
            + ([order.dealer.name] if manager else [])
            + [
                order.ordered_on.strftime("%d-%m-%Y"),
                order.raised_by,
                order.total_qty,
                order.total_net,
                order.total_gst,
                order.total_amount,
                order.get_status_display(),
            ]
        )
    return columns, rows


def _order_gst(ctx):
    """Order with GST Details.

    Unlike the screen, the columns that do not apply carry 0.00 rather than a
    dash: a spreadsheet is going to be summed, and a dash in a money column
    stops that working.
    """
    manager = ctx["is_manager"]
    columns = ["Order No"] + (["Dealer"] if manager else []) + [
        "Date", "Tax Type", "Taxable", "CGST", "SGST", "IGST", "GST", "Total",
    ]
    rows = []
    for row in ctx["rows"]:
        order = row["order"]
        rows.append(
            [order.order_no]
            + ([order.dealer.name] if manager else [])
            + [
                order.ordered_on.strftime("%d-%m-%Y"),
                row["tax_type"],
                row["net"],
                row["cgst"],
                row["sgst"],
                row["igst"],
                row["gst"],
                row["total"],
            ]
        )
    return columns, rows


def _pending_payment(ctx):
    manager = ctx["is_manager"]
    columns = ["Order No"] + (["Dealer"] if manager else []) + [
        "Date", "Raised By", "Order Total", "Received", "Balance Due", "State",
    ]
    rows = []
    for row in ctx["rows"]:
        order = row["order"]
        rows.append(
            [order.order_no]
            + ([order.dealer.name] if manager else [])
            + [
                order.ordered_on.strftime("%d-%m-%Y"),
                order.raised_by,
                row["total"],
                row["paid"],
                row["balance"],
                "Part paid" if row["paid"] > 0 else "Unpaid",
            ]
        )
    return columns, rows


def _top_orders(ctx):
    manager = ctx["is_manager"]
    columns = ["#", "Order No"] + (["Dealer"] if manager else []) + [
        "Date", "Raised By", "Items", "Net", "GST", "Total",
    ]
    rows = []
    for row in ctx["rows"]:
        order = row["order"]
        rows.append(
            [row["rank"], order.order_no]
            + ([order.dealer.name] if manager else [])
            + [
                order.ordered_on.strftime("%d-%m-%Y"),
                order.raised_by,
                order.total_qty,
                order.total_net,
                order.total_gst,
                order.total_amount,
            ]
        )
    return columns, rows


def _due_count(ctx):
    manager = ctx["is_manager"]
    columns = ["Order No"] + (["Dealer"] if manager else []) + [
        "Ordered", "Raised By", "Age (days)", "Bucket", "Order Total",
        "Received", "Balance Due",
    ]
    rows = []
    for row in ctx["rows"]:
        order = row["order"]
        rows.append(
            [order.order_no]
            + ([order.dealer.name] if manager else [])
            + [
                order.ordered_on.strftime("%d-%m-%Y"),
                order.raised_by,
                row["days"],
                row["bucket"],
                row["total"],
                row["paid"],
                row["balance"],
            ]
        )
    return columns, rows


def _top_items(ctx):
    columns = ["#", "Item", "Part No", "Brand", "Qty", "Unit", "Orders",
               "Taxable", "GST", "Total"]
    rows = [
        [row["rank"], row["name"], row["partno"], row["brand"], row["qty"],
         row["unit"], row["orders"], row["net"], row["gst"], row["total"]]
        for row in ctx["rows"]
    ]
    return columns, rows


def _order_wise_items(ctx):
    manager = ctx["is_manager"]
    columns = ["Order No"] + (["Dealer"] if manager else []) + [
        "Date", "Raised By", "#", "Item", "Part No", "Qty", "Unit",
        "Taxable", "Line Total",
    ]
    rows = []
    for group in ctx["groups"]:
        order = group["order"]
        for row in group["lines"]:
            line = row["line"]
            # the order number repeats on every line here: a spreadsheet gets
            # sorted and filtered, and a blank cell would strand the row
            rows.append(
                [order.order_no]
                + ([order.dealer.name] if manager else [])
                + [
                    order.ordered_on.strftime("%d-%m-%Y"),
                    order.raised_by,
                    row["rank"],
                    line.product.name,
                    line.product.partno,
                    line.qty,
                    str(line.product.unit),
                    row["net"],
                    row["total"],
                ]
            )
    return columns, rows


def _item_movement(ctx):
    columns = ["Item", "Part No", "Brand", "Qty", "Unit", "Orders", "Value",
               "Last Ordered", "Idle (days)", "Movement"]
    rows = [
        [row["name"], row["partno"], row["brand"], row["qty"], row["unit"],
         row["orders"], row["total"],
         row["last_on"].strftime("%d-%m-%Y") if row["last_on"] else "",
         row["idle_days"], row["band_label"]]
        for row in ctx["rows"]
    ]
    return columns, rows


def _item_summary(ctx):
    columns = ["Item", "Part No", "Brand", "Orders", "Qty", "Unit", "Avg Rate",
               "Taxable", "GST", "Total", "First Ordered", "Last Ordered"]
    rows = [
        [row["name"], row["partno"], row["brand"], row["orders"], row["qty"],
         row["unit"], row["avg_rate"], row["net"], row["gst"], row["total"],
         row["first_on"].strftime("%d-%m-%Y") if row["first_on"] else "",
         row["last_on"].strftime("%d-%m-%Y") if row["last_on"] else ""]
        for row in ctx["rows"]
    ]
    return columns, rows


# --- sales executive reports ---


def _sales_performance(ctx):
    columns = ["#", "Sales Executive", "Code", "Orders", "Dealers", "Qty",
               "Avg Order", "Taxable", "GST", "Total", "Share %"]
    rows = [
        [r["rank"], r["name"], r["code"], r["orders"], r["dealers"], r["qty"],
         r["avg_order"], r["net"], r["gst"], r["total"], r["share"]]
        for r in ctx["rows"]
    ]
    return columns, rows


def _sales_dealers(ctx):
    columns = ["Sales Executive", "Code", "Dealer", "State", "Orders", "Qty",
               "Total", "Last Order"]
    # the name repeats on every line here: a spreadsheet gets sorted, and a
    # blank cell would strand the row from its group
    rows = [
        [r["name"], r["code"], r["dealer"], r["state"], r["orders"], r["qty"],
         r["total"], r["last_on"].strftime("%d-%m-%Y") if r["last_on"] else ""]
        for r in ctx["rows"]
    ]
    return columns, rows


def _sales_comparison(ctx):
    columns = ["Sales Executive", "Code", "Orders Before", "Orders Now",
               "Value Before", "Value Now", "Change", "Change %", "Trend"]
    rows = [
        [r["name"], r["code"], r["was_orders"], r["now_orders"],
         r["was_total"], r["now_total"], r["change"],
         r["percent"] if r["percent"] is not None else "", r["direction"]]
        for r in ctx["rows"]
    ]
    return columns, rows


def _sales_items(ctx):
    columns = ["Sales Executive", "Code", "Item", "Part No", "Brand", "Qty",
               "Unit", "Orders", "Taxable", "Total"]
    rows = [
        [r["name"], r["code"], r["item"], r["partno"], r["brand"], r["qty"],
         r["unit"], r["orders"], r["net"], r["total"]]
        for r in ctx["rows"]
    ]
    return columns, rows


def _sales_collection(ctx):
    columns = ["Sales Executive", "Code", "Orders", "Billed", "Received",
               "Outstanding", "Unpaid Orders", "Collected %"]
    rows = [
        [r["name"], r["code"], r["orders"], r["billed"], r["received"],
         r["outstanding"], r["overdue_orders"], r["collected_pc"]]
        for r in ctx["rows"]
    ]
    return columns, rows


def _visit_report(ctx):
    columns = ["Date", "Time", "Dealer", "Sales Executive", "Code", "Visit No",
               "Place", "Latitude", "Longitude", "Accuracy (m)", "Map", "Note"]
    rows = []
    for v in ctx["rows"]:
        rows.append([
            v.visited_on.strftime("%d-%m-%Y"),
            v.created_at.strftime("%H:%M"),
            v.dealer.name,
            v.sales_executive.name,
            v.sales_executive.code,
            v.visit_no,
            v.place,
            v.latitude, v.longitude, v.accuracy_m,
            # a clickable link in the sheet beats a pair of numbers
            v.map_url,
            v.note,
        ])
    return columns, rows


# slug -> the function that flattens that report
BUILDERS = {
    "order-book": _order_book,
    "pending-payment": _pending_payment,
    "top-orders": _top_orders,
    "due-count": _due_count,
    "top-items": _top_items,
    "order-wise-items": _order_wise_items,
    "item-movement": _item_movement,
    "item-summary": _item_summary,
    "order-gst": _order_gst,
    "sales-performance": _sales_performance,
    "sales-dealers": _sales_dealers,
    "sales-comparison": _sales_comparison,
    "sales-items": _sales_items,
    "sales-collection": _sales_collection,
    "visit-report": _visit_report,
}


# the context entries a report's rows can arrive under
ROW_KEYS = ("orders", "rows", "groups")


def _whole_report(context):
    """The context with its rows put back to the full set.

    A report page shows a hundred rows at a time, so the entry the table
    iterates holds only the current page. views._paginate keeps the whole list
    beside it as "all_<key>". An export is of the report, not of whichever page
    the person happened to be looking at, so swap the full list back in.

    A copy, because the response's own context must keep the page it rendered.
    """
    whole = dict(context)
    for key in ROW_KEYS:
        everything = context.get("all_" + key)
        if everything is not None:
            whole[key] = everything
    return whole


def table_for(slug, context):
    """(columns, rows) for one report, from the context its page renders."""
    build = BUILDERS.get(slug)
    if build is None:
        raise Http404(f"No export for report '{slug}'.")
    return build(_whole_report(context))


# --------------------------------------------------------------- writers


def _filename(card, fmt):
    """reports-order-book-2026-09-21.csv"""
    stamp = timezone.localdate().isoformat()
    return f"{card['slug']}-{stamp}.{fmt}"


def to_csv(card, columns, rows, subtitle):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{_filename(card, "csv")}"'

    writer = csv.writer(response)
    # two lines of provenance first, so a file on someone's desktop still says
    # which report it is and what it was filtered to
    writer.writerow([card["name"]])
    writer.writerow([subtitle])
    writer.writerow([])
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_text(cell) for cell in row])
    return response


def to_excel(card, columns, rows, subtitle):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    book = Workbook()
    sheet = book.active
    # a sheet name may not exceed 31 characters or hold []:*?/\
    sheet.title = card["name"][:31].replace("/", "-")

    sheet.append([card["name"]])
    sheet["A1"].font = Font(bold=True, size=13)
    sheet.append([subtitle])
    sheet["A2"].font = Font(italic=True, color="6B7280")
    sheet.append([])

    head_row = sheet.max_row + 1
    sheet.append(columns)
    for cell in sheet[head_row]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1D4E89")
        cell.alignment = Alignment(vertical="center")

    for row in rows:
        sheet.append(list(row))

    # rough auto-width from the longest value in each column
    for index, name in enumerate(columns, start=1):
        longest = max([len(str(name))] + [len(_text(r[index - 1])) for r in rows] or [0])
        letter = sheet.cell(row=head_row, column=index).column_letter
        sheet.column_dimensions[letter].width = min(longest + 2, MAX_COL_WIDTH)

    # freeze everything above the first data row, so the headings stay put
    sheet.freeze_panes = f"A{head_row + 1}"

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{_filename(card, "xlsx")}"'
    book.save(response)
    return response


def to_pdf(card, columns, rows, subtitle):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
        title=f"{card['name']} {timezone.localdate():%d %b %Y}",
    )
    styles = getSampleStyleSheet()

    # landscape A4 is 277mm of usable width; a report with a dozen columns
    # needs a small face to fit, so the size follows the column count
    size = 8 if len(columns) <= 9 else 7 if len(columns) <= 11 else 6

    data = [columns] + [[_text(cell) for cell in row] for row in rows]

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4e89")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), size),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    doc.build([
        Paragraph(card["name"], styles["Heading2"]),
        Paragraph(subtitle, styles["Normal"]),
        Spacer(1, 8),
        table,
    ])

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{_filename(card, "pdf")}"'
    return response


WRITERS = {"csv": to_csv, "excel": to_excel, "pdf": to_pdf}
