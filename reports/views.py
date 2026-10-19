"""The eight reports, plus the card index that leads to them.

House rules followed throughout:

* Reports only read. Nothing here writes to the database.
* Who may see whose orders is decided by myorder's own rule, reused through
  services.report_orders() — a report must never widen a dealer's view.
* A report counts placed (Final) orders unless it says otherwise. A draft is
  still being edited; it is not business that happened.
* All money is added up in Python from the model's own line_net / line_gst,
  never with a database SUM over the raw arithmetic. The model rounds each
  line and the invoice is printed from those rounded figures, so anything
  that rounds differently ends up disagreeing with the invoice by a paisa or
  two. It also avoids the fan-out you get from summing items and payments in
  one query.
* Every amount a report prints goes through services.money(), so all of them
  read at two decimals.
"""

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.template.response import TemplateResponse
from django.utils import timezone

from delaer.models import DealerProfile, SalesExecutive
from payment.models import order_paid
from products.models import Product

from . import exports
from .services import (
    PERIOD_MONTH,
    PERIOD_YEAR,
    _company,
    _sales,
    _same_state,
    apply_dates,
    is_manager,
    match_row,
    money,
    order_items,
    period_params,
    read_filter,
    report_orders,
    search_orders,
)

ZERO = Decimal("0.00")


# ------------------------------------------------------------------ index

# One entry per report: the name shown on the card and as the page heading,
# the icon and tint for the card, and the route it opens. The name is used in
# both places, so a card and the page it opens can never drift apart.
REPORT_CARDS = [
    {
        "slug": "order-book",
        "url": "reports:order_book",
        "name": "Order Book",
        "icon": "book-outline",
        "tint": "var(--primary-500)",
    },
    {
        "slug": "pending-payment",
        "url": "reports:pending_payment",
        "name": "Order Book with Pending Payment",
        "icon": "hourglass-outline",
        "tint": "var(--warning)",
    },
    {
        "slug": "top-orders",
        "url": "reports:top_orders",
        "name": "Top Order Records",
        "icon": "trending-up-outline",
        "tint": "var(--success)",
    },
    {
        "slug": "due-count",
        "url": "reports:due_count",
        "name": "Order Book Due Count Details",
        "icon": "alarm-outline",
        "tint": "var(--danger)",
    },
    {
        "slug": "top-items",
        "url": "reports:top_items",
        "name": "Top Order Item by You",
        "icon": "ribbon-outline",
        "tint": "var(--info)",
    },
    {
        "slug": "order-wise-items",
        "url": "reports:order_wise_items",
        "name": "Top Order Wise Item Wise",
        "icon": "list-outline",
        "tint": "var(--primary-600)",
    },
    {
        "slug": "item-movement",
        "url": "reports:item_movement",
        "name": "Order Item Slow Moving Fast Moving",
        "icon": "speedometer-outline",
        "tint": "var(--accent-600, var(--primary-600))",
    },
    {
        "slug": "item-summary",
        "url": "reports:item_summary",
        "name": "Item Wise Order Summary",
        "icon": "cube-outline",
        "tint": "var(--warning)",
    },
    {
        "slug": "order-gst",
        "url": "reports:order_gst",
        "name": "Order with GST Details",
        "icon": "receipt-outline",
        "tint": "var(--danger)",
    },

    # --- sales executive ---
    {
        "slug": "sales-performance",
        "url": "reports:sales_performance",
        "name": "Sales Executive Performance",
        "icon": "podium-outline",
        "tint": "var(--success)",
    },
    {
        "slug": "sales-dealers",
        "url": "reports:sales_dealers",
        "name": "Sales Executive wise Dealer",
        "icon": "people-outline",
        "tint": "var(--info)",
    },
    {
        "slug": "sales-comparison",
        "url": "reports:sales_comparison",
        "name": "Sales Executive Comparison",
        "icon": "git-compare-outline",
        "tint": "var(--primary-600)",
    },
    {
        "slug": "sales-items",
        "url": "reports:sales_items",
        "name": "Sales Executive Item Mix",
        "icon": "layers-outline",
        "tint": "var(--accent-600, var(--primary-600))",
    },
    {
        "slug": "sales-collection",
        "url": "reports:sales_collection",
        "name": "Sales Executive Collection",
        "icon": "cash-outline",
        "tint": "var(--danger)",
    },
    {
        "slug": "visit-report",
        "url": "reports:visit_report",
        "name": "Sales Executive Visit Report",
        "icon": "map-outline",
        "tint": "var(--info)",
    },
]


@login_required
def reports(request):
    """The report index — one card per report."""
    return render(request, "reports/reports.html", {"cards": REPORT_CARDS})


# ------------------------------------------------------- shared page setup


# How many rows a page of a report shows. The product list already uses 100,
# so every long table in the project now agrees.
PER_PAGE = 100


def _paginate(request, context, key):
    """Cut a report's rows into pages of PER_PAGE.

    `key` names the context entry holding the rows — "orders" for the order
    book, "rows" for most, "groups" for the order-wise report.

    Two things stay whole on purpose:

    * the totals in the footer. Each view works them out before calling this,
      over every matching row, so the figures describe the report and not just
      the hundred rows in front of you.
    * the export. The full list is kept under "all_<key>", and exports.py
      reads that, so a CSV is still the whole report.
    """
    rows = context.get(key) or []

    paginator = Paginator(rows, PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))

    # "1 2 … 5 6 7 … 20". Built here because a template cannot hand the current
    # page number to get_elided_page_range().
    page_range = paginator.get_elided_page_range(page.number, on_each_side=1,
                                                 on_ends=1)

    # the page links have to carry the filter, or page 2 would show the
    # unfiltered report
    params = request.GET.copy()
    params.pop("page", None)

    context["all_" + key] = rows      # kept whole for the exports
    context[key] = page.object_list   # what the table iterates
    context["page"] = page
    context["page_range"] = page_range
    context["querystring"] = params.urlencode()
    return context


def _page(request, filters, *, slug, extra=None, paginate=None):
    """The context every report page needs: the toolbar's state, who is
    looking, and which card this page belongs to.

    `paginate` names the context entry holding the report's rows; pass it and
    the table is cut into pages of PER_PAGE.
    """
    card = next(c for c in REPORT_CARDS if c["slug"] == slug)

    context = {
        **filters,
        "card": card,
        "is_manager": is_manager(request.user),
        # the dealer dropdown is only offered to someone who can see more
        # than their own orders
        "dealers": DealerProfile.objects.all() if is_manager(request.user) else None,
        # a manager can attribute the report to one salesman; a salesman is
        # already limited to their own and needs no picker
        "sales_people": SalesExecutive.objects.all() if is_manager(request.user) else None,
    }
    context.update(extra or {})

    if paginate:
        _paginate(request, context, paginate)

    return context


def _totals(orders):
    """Net, GST, total and quantity across a list of orders.

    The model already rounds each line, so these sums are on paise already.
    """
    return {
        "net": sum((o.total_net for o in orders), ZERO),
        "gst": sum((o.total_gst for o in orders), ZERO),
        "total": sum((o.total_amount for o in orders), ZERO),
        "qty": sum(o.total_qty for o in orders),
    }


def _with_payment(orders):
    """Attach paid and balance to each order.

    Done here rather than in the template so the numbers can be searched,
    sorted and totalled like any other column.
    """
    rows = []
    for order in orders:
        total = order.total_amount
        paid = order_paid(order)
        rows.append({
            "order": order,
            "total": total,
            "paid": paid,
            # never negative: an overpayment is dealer credit, not a minus due
            "balance": max(total - paid, ZERO),
        })
    return rows


# ------------------------------------------------------------ 1. Order Book


@login_required
def order_book(request):
    """Every placed order, same columns as the order table."""
    filters = read_filter(request)

    # prefetch the lines: total_net / total_gst / total_amount all walk them,
    # and without this each order would cost its own query
    orders = report_orders(request, filters).prefetch_related("items__product")
    orders = search_orders(list(orders), filters["search"])

    return TemplateResponse(request, "reports/order_book.html", _page(
        request, filters, slug="order-book", paginate="orders",
        extra={"orders": orders, "totals": _totals(orders)},
    ))


# ------------------------------------ 2. Order Book with Pending Payment


@login_required
def pending_payment(request):
    """Placed orders that still owe money."""
    filters = read_filter(request)

    orders = (
        report_orders(request, filters)
        .prefetch_related("items__product", "payments")
    )
    orders = search_orders(list(orders), filters["search"])

    # balance comes from the order total against its receipts, so it cannot be
    # filtered in SQL — the total is built from the lines, not stored
    rows = [row for row in _with_payment(orders) if row["balance"] > ZERO]
    # worst first: the biggest outstanding amount is the one to chase
    rows.sort(key=lambda r: r["balance"], reverse=True)

    return TemplateResponse(request, "reports/pending_payment.html", _page(
        request, filters, slug="pending-payment", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "total": sum((r["total"] for r in rows), ZERO),
                "paid": sum((r["paid"] for r in rows), ZERO),
                "balance": sum((r["balance"] for r in rows), ZERO),
            },
        },
    ))


# ----------------------------------------------------- 3. Top Order Records


@login_required
def top_orders(request):
    """The order book ranked by value, biggest first."""
    filters = read_filter(request)

    orders = report_orders(request, filters).prefetch_related("items__product")
    orders = search_orders(list(orders), filters["search"])
    orders.sort(key=lambda o: o.total_amount, reverse=True)

    # rank is worked out here so the template does not have to count
    rows = [{"rank": i, "order": o} for i, o in enumerate(orders, start=1)]

    return TemplateResponse(request, "reports/top_orders.html", _page(
        request, filters, slug="top-orders", paginate="rows",
        extra={"rows": rows, "totals": _totals(orders)},
    ))


# --------------------------------------- 4. Order Book Due Count Details


# (label, lowest day in the bucket, highest day or None for "and above")
AGE_BUCKETS = [
    ("0–30 days", 0, 30),
    ("31–60 days", 31, 60),
    ("61–90 days", 61, 90),
    ("90+ days", 91, None),
]


def _bucket_for(days):
    """Which ageing bucket an unpaid order falls into."""
    for label, low, high in AGE_BUCKETS:
        if days >= low and (high is None or days <= high):
            return label
    return AGE_BUCKETS[0][0]


@login_required
def due_count(request):
    """Unpaid balances by age, with a count and a total per bucket."""
    filters = read_filter(request)
    today = timezone.localdate()

    orders = (
        report_orders(request, filters)
        .prefetch_related("items__product", "payments")
    )
    orders = search_orders(list(orders), filters["search"])

    rows = []
    for row in _with_payment(orders):
        if row["balance"] <= ZERO:
            continue
        days = (today - row["order"].ordered_on).days
        rows.append({**row, "days": days, "bucket": _bucket_for(days)})

    # oldest debt first — that is the order of a collection call list
    rows.sort(key=lambda r: r["days"], reverse=True)

    # the summary strip above the table: how many and how much in each band
    summary = []
    for label, _low, _high in AGE_BUCKETS:
        in_band = [r for r in rows if r["bucket"] == label]
        summary.append({
            "label": label,
            "count": len(in_band),
            "amount": sum((r["balance"] for r in in_band), ZERO),
        })

    return TemplateResponse(request, "reports/due_count.html", _page(
        request, filters, slug="due-count", paginate="rows",
        extra={
            "rows": rows,
            "summary": summary,
            "totals": {
                "count": len(rows),
                "order_total": sum((r["total"] for r in rows), ZERO),
                "paid": sum((r["paid"] for r in rows), ZERO),
                "balance": sum((r["balance"] for r in rows), ZERO),
            },
        },
    ))


# ----------------------------------------------- 5. Top Order Item by You


def _item_totals(request, filters):
    """Per-product totals across the period, straight from the database.

    One row per product: quantity, how many orders it appeared on, taxable
    value, GST, and when it was first and last ordered. Returned as plain
    dicts with short keys, so the three reports that use this and their
    templates all read the same way.

    Grouped in Python from OrderItem's own line_net / line_gst rather than
    with a database SUM. That is deliberate and it is about agreeing with the
    rest of the system, not about convenience:

    the model rounds the GST of every line, and the invoice is printed from
    those rounded figures. Summing the unrounded product in SQL instead made
    these reports disagree with the order reports about the same orders —
    365,444.91 against 365,444.89. Rounding per line in SQL closed most of
    the gap but not all of it, because SQLite's ROUND works in floating point
    while the model rounds exact decimals. Using the model's own property is
    the only way the two agree by construction rather than by luck.
    """
    grouped = {}

    for line in order_items(request, filters):
        product = line.product
        row = grouped.get(product.pk)
        if row is None:
            row = grouped[product.pk] = {
                "product_id": product.pk,
                "name": product.name,
                "partno": product.partno,
                "brand": str(product.brand),
                "unit": str(product.unit),
                "qty": 0,
                # a product can appear on one order once, but count distinct
                # orders rather than lines so "Orders" means what it says
                "order_ids": set(),
                "net": ZERO,
                "gst": ZERO,
                "first_on": None,
                "last_on": None,
            }

        ordered_on = line.order.ordered_on
        row["qty"] += line.qty
        row["order_ids"].add(line.order_id)
        row["net"] += line.line_net
        row["gst"] += line.line_gst
        row["first_on"] = min(row["first_on"] or ordered_on, ordered_on)
        row["last_on"] = max(row["last_on"] or ordered_on, ordered_on)

    totals = []
    for row in grouped.values():
        row["orders"] = len(row.pop("order_ids"))
        row["total"] = row["net"] + row["gst"]
        totals.append(row)
    return totals


@login_required
def top_items(request):
    """Which products get ordered the most, by quantity."""
    filters = read_filter(request)

    rows = _item_totals(request, filters)
    # most taken first; name breaks a tie so the order never jitters
    rows.sort(key=lambda r: (-r["qty"], r["name"]))

    rows = [r for r in rows if match_row(r, filters["search"], "name", "partno", "brand")]

    # rank after filtering, so the numbering always starts at 1
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank

    return TemplateResponse(request, "reports/top_items.html", _page(
        request, filters, slug="top-items", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "qty": sum(r["qty"] for r in rows),
                # every line this item appeared on, across all its orders
                "orders": sum(r["orders"] for r in rows),
                "net": sum((r["net"] for r in rows), ZERO),
                "total": sum((r["total"] for r in rows), ZERO),
            },
        },
    ))


# ------------------------------------------ 6. Top Order Wise Item Wise


@login_required
def order_wise_items(request):
    """Every order opened up, with its own lines ranked by value.

    Orders are ordered by what they came to, biggest first; inside each one
    the lines are ranked the same way. The table repeats the order number on
    its first line only, so it reads as groups rather than a flat list.
    """
    filters = read_filter(request)

    lines = order_items(request, filters)

    # group the lines by their order in one pass
    by_order = defaultdict(list)
    for line in lines:
        by_order[line.order_id].append(line)

    groups = []
    for order_lines in by_order.values():
        order = order_lines[0].order
        # biggest line first inside the order
        order_lines.sort(key=lambda line: line.line_net, reverse=True)

        # the model's own per-line figures, the same ones the order page and
        # the invoice print, so a group total here equals that order's total
        rows = []
        for rank, line in enumerate(order_lines, start=1):
            rows.append({
                "rank": rank,
                "line": line,
                "net": line.line_net,
                "total": line.line_total,
            })

        groups.append({
            "order": order,
            "value": sum((row["total"] for row in rows), ZERO),
            "lines": rows,
        })

    groups.sort(key=lambda g: g["value"], reverse=True)

    term = filters["search"]
    if term:
        needle = term.lower()
        groups = [
            g for g in groups
            if needle in g["order"].order_no.lower()
            or needle in g["order"].dealer.name.lower()
            or any(needle in row["line"].product.name.lower() for row in g["lines"])
        ]

    return TemplateResponse(request, "reports/order_wise_items.html", _page(
        request, filters, slug="order-wise-items", paginate="groups",
        extra={
            "groups": groups,
            "totals": {
                "orders": len(groups),
                "lines": sum(len(g["lines"]) for g in groups),
                "qty": sum(row["line"].qty for g in groups for row in g["lines"]),
                "net": sum((row["net"] for g in groups for row in g["lines"]), ZERO),
                "value": sum((g["value"] for g in groups), ZERO),
            },
        },
    ))


# -------------------------------- 7. Order Item Slow Moving Fast Moving


# a product is Fast if it is in the top third by quantity, Slow in the bottom
# third, Medium in between — bands rather than fixed numbers, so the report
# still makes sense whatever the business volume is
def _movement_band(position, moving_count):
    if moving_count == 0:
        return "Slow"
    if position <= moving_count / 3:
        return "Fast"
    if position <= (moving_count * 2) / 3:
        return "Medium"
    return "Slow"


# "Idle" rather than "None" so the key is never mistaken for an empty value
BAND_BADGE = {"Fast": "success", "Medium": "warning", "Slow": "danger", "Idle": "neutral"}
BAND_LABEL = {"Fast": "Fast", "Medium": "Medium", "Slow": "Slow", "Idle": "Not ordered"}


@login_required
def item_movement(request):
    """Products banded by how fast they move, including the ones that do not."""
    filters = read_filter(request)
    today = timezone.localdate()

    moving = _item_totals(request, filters)
    moving.sort(key=lambda r: (-r["qty"], r["name"]))

    rows = []
    for position, row in enumerate(moving, start=1):
        band = _movement_band(position, len(moving))
        rows.append({
            **row,
            # how long it has sat still, which is the point of the report
            "idle_days": (today - row["last_on"]).days if row["last_on"] else None,
            "band": band,
            "badge": BAND_BADGE[band],
        })

    # products nobody ordered in this period belong in a movement report too —
    # they are the slowest movers there are
    ordered_ids = {row["product_id"] for row in moving}
    for product in Product.objects.select_related("brand", "unit").exclude(pk__in=ordered_ids):
        rows.append({
            "name": product.name,
            "partno": product.partno,
            "brand": str(product.brand),
            "unit": str(product.unit),
            "qty": 0,
            "orders": 0,
            "total": ZERO,
            "last_on": None,
            "idle_days": None,
            "band": "Idle",
            "badge": BAND_BADGE["Idle"],
        })

    for row in rows:
        row["band_label"] = BAND_LABEL[row["band"]]

    # the search applies whatever band is chosen, so count on the searched set
    rows = [r for r in rows if match_row(r, filters["search"], "name", "partno", "brand")]
    counts = {name: 0 for name in BAND_BADGE}
    for row in rows:
        counts[row["band"]] += 1

    # an explicit band filter, on top of the search box
    band = request.GET.get("band", "")
    if band in BAND_BADGE:
        rows = [r for r in rows if r["band"] == band]

    # the band links keep every other filter that is already set
    band_keep = request.GET.copy()
    band_keep.pop("band", None)
    band_keep = band_keep.urlencode()

    return TemplateResponse(request, "reports/item_movement.html", _page(
        request, filters, slug="item-movement", paginate="rows",
        extra={
            "rows": rows,
            "band": band,
            "band_keep": band_keep,
            # name, label and count together, so the template can just loop
            "band_options": [
                {"name": name, "label": BAND_LABEL[name], "count": counts[name]}
                for name in BAND_BADGE
            ],
            "counts": counts,
            "totals": {
                "qty": sum(r["qty"] for r in rows),
                "orders": sum(r["orders"] for r in rows),
                "total": sum((r["total"] for r in rows), ZERO),
            },
        },
    ))


# ------------------------------------------- 8. Item Wise Order Summary


@login_required
def item_summary(request):
    """One line per product, with everything the period says about it."""
    filters = read_filter(request)

    rows = _item_totals(request, filters)
    rows.sort(key=lambda r: r["name"])

    for row in rows:
        # what it actually went out at on average, not the list price
        row["avg_rate"] = money(row["net"] / row["qty"]) if row["qty"] else ZERO

    rows = [r for r in rows if match_row(r, filters["search"], "name", "partno", "brand")]

    return TemplateResponse(request, "reports/item_summary.html", _page(
        request, filters, slug="item-summary", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "qty": sum(r["qty"] for r in rows),
                "orders": sum(r["orders"] for r in rows),
                "net": sum((r["net"] for r in rows), ZERO),
                "gst": sum((r["gst"] for r in rows), ZERO),
                "total": sum((r["total"] for r in rows), ZERO),
                # weighted, not the mean of the per-item averages: a product
                # ordered 500 times must not count the same as one ordered once
                "avg_rate": money(
                    sum((r["net"] for r in rows), ZERO) / sum(r["qty"] for r in rows)
                ) if sum(r["qty"] for r in rows) else ZERO,
            },
        },
    ))


# -------------------------------------------- 9. Order with GST Details


# What the tax type column says, and what the search box can be typed with to
# pick out one kind of sale. Kept as constants so the table, the search and the
# export can never word it differently.
INTRA = "Intra-state (CGST + SGST)"
INTER = "Inter-state (IGST)"


def _gst_rows(orders):
    """Each order's tax split out into net, CGST, SGST, IGST and total.

    The split follows the same rule as the order page and the invoice: a dealer
    in our own state is charged CGST + SGST, half the slab each, and a dealer in
    another state is charged IGST at the whole slab. The two never appear on the
    same order, so the column that does not apply is left at zero rather than
    repeating the other one.

    _company() is read once here rather than once per order — _tax_context()
    fetches it per call, which is fine for one invoice and a query per row for a
    report of two hundred.
    """
    company = _company()
    rows = []

    for order in orders:
        same_state = _same_state(company, order.dealer)
        gst = order.total_gst
        # the odd paisa of an uneven slab lands in SGST, never lost — Order
        # does the halving so the figure matches the printed invoice exactly
        cgst, sgst = order._halve(gst)

        rows.append({
            "order": order,
            "tax_type": INTRA if same_state else INTER,
            "same_state": same_state,
            "qty": order.total_qty,
            "net": order.total_net,
            "cgst": cgst if same_state else ZERO,
            "sgst": sgst if same_state else ZERO,
            "igst": ZERO if same_state else gst,
            "gst": gst,
            "total": order.total_amount,
        })
    return rows


@login_required
def order_gst(request):
    """Every placed order with its tax worked out in full.

    The order table and the Order Book show the total only. This is the report
    to open when the GST itself is the question: what was taxable, how it split
    into CGST and SGST or carried as IGST, and what that came to.
    """
    filters = read_filter(request)

    # the split walks the lines for net and GST, so pull them in one query
    orders = report_orders(request, filters).prefetch_related("items__product")

    rows = _gst_rows(orders)

    # searched on the built rows rather than the orders, so "igst" or "intra"
    # finds a kind of sale as readily as an order number or a dealer finds one
    term = filters["search"]
    rows = [
        r for r in rows
        if not term
        or term.lower() in r["order"].order_no.lower()
        or term.lower() in r["order"].dealer.name.lower()
        or match_row(r, term, "tax_type")
    ]

    return TemplateResponse(request, "reports/order_gst.html", _page(
        request, filters, slug="order-gst", paginate="rows",
        extra={
            "rows": rows,
            # totalled over every matching order, not just the page on screen
            "totals": {
                "orders": len(rows),
                "qty": sum(r["qty"] for r in rows),
                "net": sum((r["net"] for r in rows), ZERO),
                "cgst": sum((r["cgst"] for r in rows), ZERO),
                "sgst": sum((r["sgst"] for r in rows), ZERO),
                "igst": sum((r["igst"] for r in rows), ZERO),
                "gst": sum((r["gst"] for r in rows), ZERO),
                "total": sum((r["total"] for r in rows), ZERO),
                # how the period split between the two kinds of sale
                "intra": sum(1 for r in rows if r["same_state"]),
                "inter": sum(1 for r in rows if not r["same_state"]),
            },
        },
    ))


# ======================================================================
#  Sales executive reports
#
#  Five views of the same question: who is bringing the business in.
#
#  Visibility needs no special handling — report_orders() goes through
#  myorder's _visible_orders(), which already leaves a salesman only the
#  orders raised in their name. A salesman opening any of these sees their
#  own figures; a manager sees everyone and can narrow with the picker.
#
#  An order with no salesman is real business, not missing data: the dealer
#  placed it themselves. It is reported as "Direct" rather than dropped.
# ======================================================================

DIRECT = "Direct (dealer's own)"


def _credit(order):
    """Who an order counts towards, and under what name."""
    if order.sales_executive_id:
        return order.sales_executive_id, order.sales_executive.name, order.sales_executive.code
    return None, DIRECT, "—"


def _sales_rows(request, filters, orders=None):
    """One row per salesman across the period: orders, dealers, money.

    Grouped in Python from the orders' own totals, like every other money
    figure in this module, so these agree with the order book exactly.
    """
    orders = report_orders(request, filters) if orders is None else orders

    grouped = {}
    for order in orders:
        key, name, code = _credit(order)
        row = grouped.get(key)
        if row is None:
            row = grouped[key] = {
                "sales_id": key,
                "name": name,
                "code": code,
                "orders": 0,
                "dealer_ids": set(),
                "qty": 0,
                "net": ZERO,
                "gst": ZERO,
                "total": ZERO,
                "first_on": None,
                "last_on": None,
            }
        row["orders"] += 1
        row["dealer_ids"].add(order.dealer_id)
        row["qty"] += order.total_qty
        row["net"] += order.total_net
        row["gst"] += order.total_gst
        row["total"] += order.total_amount
        row["first_on"] = min(row["first_on"] or order.ordered_on, order.ordered_on)
        row["last_on"] = max(row["last_on"] or order.ordered_on, order.ordered_on)

    rows = []
    for row in grouped.values():
        row["dealers"] = len(row.pop("dealer_ids"))
        # what an average order from this person is worth — the figure that
        # separates someone writing many small orders from a few large ones
        row["avg_order"] = money(row["total"] / row["orders"]) if row["orders"] else ZERO
        rows.append(row)
    return rows


# --------------------------------------------- 9. Sales Executive Performance


@login_required
def sales_performance(request):
    """Each salesman's book for the period, biggest first."""
    filters = read_filter(request)

    rows = _sales_rows(request, filters)
    rows.sort(key=lambda r: r["total"], reverse=True)
    rows = [r for r in rows if match_row(r, filters["search"], "name", "code")]

    carry = period_params(filters)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
        # step one of the drill-down: this executive's dealers, same period
        row["drill"] = urlencode({**carry, "sales": row["sales_id"] or "direct"})
        # each person's share of the period, so the table reads as a split
        row["share"] = (
            money(row["total"] * 100 / sum((x["total"] for x in rows), ZERO))
            if sum((x["total"] for x in rows), ZERO) else ZERO
        )

    return TemplateResponse(request, "reports/sales_performance.html", _page(
        request, filters, slug="sales-performance", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "orders": sum(r["orders"] for r in rows),
                "qty": sum(r["qty"] for r in rows),
                "net": sum((r["net"] for r in rows), ZERO),
                "gst": sum((r["gst"] for r in rows), ZERO),
                "total": sum((r["total"] for r in rows), ZERO),
            },
        },
    ))


# ------------------------------------------ 10. Sales Executive wise Dealer


@login_required
def sales_dealers(request):
    """Which dealers each salesman is actually selling to.

    One row per salesman-and-dealer pair, so a book that looks healthy in
    total but rests on a single account shows it.
    """
    filters = read_filter(request)

    grouped = {}
    for order in report_orders(request, filters):
        key, name, code = _credit(order)
        pair = (key, order.dealer_id)
        row = grouped.get(pair)
        if row is None:
            row = grouped[pair] = {
                "name": name,
                "code": code,
                # the ids behind the names, so a row can link to the orders
                # it is made of — see the drill-down block below
                "sales_id": key,
                "dealer_id": order.dealer_id,
                "dealer": order.dealer.name,
                "state": order.dealer.state or "—",
                "orders": 0,
                "qty": 0,
                "total": ZERO,
                "last_on": None,
            }
        row["orders"] += 1
        row["qty"] += order.total_qty
        row["total"] += order.total_amount
        row["last_on"] = max(row["last_on"] or order.ordered_on, order.ordered_on)

    rows = sorted(grouped.values(), key=lambda r: (r["name"], -r["total"]))
    rows = [r for r in rows if match_row(r, filters["search"], "name", "code", "dealer", "state")]

    # the first row of each salesman carries the name; the rest read as a
    # group under it, the way the order-wise report does
    seen = set()
    carry = period_params(filters)
    for row in rows:
        row["first_of_group"] = row["name"] not in seen
        seen.add(row["name"])

        # clicking the dealer opens the order book holding exactly the orders
        # this row counts — same dealer, same executive, same period — and
        # each order there opens in full from its own view icon
        row["drill"] = urlencode({
            **carry,
            "dealer": row["dealer_id"],
            "sales": row["sales_id"] or "direct",
        })

    return TemplateResponse(request, "reports/sales_dealers.html", _page(
        request, filters, slug="sales-dealers", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "pairs": len(rows),
                "orders": sum(r["orders"] for r in rows),
                "qty": sum(r["qty"] for r in rows),
                "total": sum((r["total"] for r in rows), ZERO),
            },
        },
    ))


# ------------------------------------------- 11. Sales Executive Comparison


def _previous_period(filters):
    """The stretch of time this period should be measured against.

    A calendar period compares with the calendar period before it: September
    against the whole of August, 2026 against the whole of 2025. Counting
    back a fixed number of days instead would have pitted September's 30 days
    against 2–31 August, quietly dropping the 1st and flattering the month.

    A custom range has no calendar meaning, so that one does count back the
    same number of days. "All time" has nothing before it at all.
    """
    start, end = filters["date_from"], filters["date_to"]
    if not (start and end):
        return None, None

    if filters["period"] == PERIOD_MONTH:
        last_day_before = start - timedelta(days=1)
        return last_day_before.replace(day=1), last_day_before

    if filters["period"] == PERIOD_YEAR:
        year = start.year - 1
        return date(year, 1, 1), date(year, 12, 31)

    span = (end - start).days + 1
    return start - timedelta(days=span), start - timedelta(days=1)


@login_required
def sales_comparison(request):
    """This period against the one before it, per salesman."""
    filters = read_filter(request)

    now_rows = {r["name"]: r for r in _sales_rows(request, filters)}

    # the same query, wound back one period
    was_rows = {}
    prev_from, prev_to = _previous_period(filters)
    if prev_from:
        earlier = dict(filters, date_from=prev_from, date_to=prev_to)
        was_rows = {r["name"]: r for r in _sales_rows(request, earlier)}

    rows = []
    for name in sorted(set(now_rows) | set(was_rows)):
        now = now_rows.get(name)
        was = was_rows.get(name)
        now_total = now["total"] if now else ZERO
        was_total = was["total"] if was else ZERO
        change = now_total - was_total

        rows.append({
            "name": name,
            "code": (now or was)["code"],
            "now_orders": now["orders"] if now else 0,
            "was_orders": was["orders"] if was else 0,
            "now_total": now_total,
            "was_total": was_total,
            "change": change,
            # no percentage against a period with nothing in it — "up 100%"
            # from zero says less than plainly showing it is new business
            "percent": money(change * 100 / was_total) if was_total else None,
            "direction": "up" if change > 0 else "down" if change < 0 else "flat",
        })

    rows.sort(key=lambda r: r["now_total"], reverse=True)
    rows = [r for r in rows if match_row(r, filters["search"], "name", "code")]

    return TemplateResponse(request, "reports/sales_comparison.html", _page(
        request, filters, slug="sales-comparison", paginate="rows",
        extra={
            "rows": rows,
            "has_previous": bool(prev_from),
            "previous_label": (f"{prev_from:%d %b %Y} – {prev_to:%d %b %Y}"
                               if prev_from else ""),
            "totals": {
                "now_total": sum((r["now_total"] for r in rows), ZERO),
                "was_total": sum((r["was_total"] for r in rows), ZERO),
                "change": sum((r["change"] for r in rows), ZERO),
                "now_orders": sum(r["now_orders"] for r in rows),
                "was_orders": sum(r["was_orders"] for r in rows),
            },
        },
    ))


# --------------------------------------------- 12. Sales Executive Item Mix


@login_required
def sales_items(request):
    """What each salesman actually sells.

    One row per salesman-and-product pair. Two people with the same turnover
    can be selling quite different things, and that only shows here.
    """
    filters = read_filter(request)

    grouped = {}
    for line in order_items(request, filters):
        order = line.order
        key, name, code = _credit(order)
        pair = (key, line.product_id)
        row = grouped.get(pair)
        if row is None:
            row = grouped[pair] = {
                "name": name,
                "code": code,
                "item": line.product.name,
                "partno": line.product.partno,
                "brand": str(line.product.brand),
                "unit": str(line.product.unit),
                "qty": 0,
                "order_ids": set(),
                "net": ZERO,
                "total": ZERO,
            }
        row["qty"] += line.qty
        row["order_ids"].add(line.order_id)
        row["net"] += line.line_net
        row["total"] += line.line_total

    rows = []
    for row in grouped.values():
        row["orders"] = len(row.pop("order_ids"))
        rows.append(row)

    rows.sort(key=lambda r: (r["name"], -r["total"]))
    rows = [
        r for r in rows
        if match_row(r, filters["search"], "name", "code", "item", "partno", "brand")
    ]

    seen = set()
    for row in rows:
        row["first_of_group"] = row["name"] not in seen
        seen.add(row["name"])

    return TemplateResponse(request, "reports/sales_items.html", _page(
        request, filters, slug="sales-items", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "pairs": len(rows),
                "qty": sum(r["qty"] for r in rows),
                "net": sum((r["net"] for r in rows), ZERO),
                "total": sum((r["total"] for r in rows), ZERO),
            },
        },
    ))


# ------------------------------------------- 13. Sales Executive Collection


@login_required
def sales_collection(request):
    """What each salesman has brought in against what they have billed.

    Turnover on its own flatters anyone whose dealers do not pay. This puts
    the money received and the money still owed beside the order value, so
    the two are read together.
    """
    filters = read_filter(request)

    orders = report_orders(request, filters).prefetch_related("payments")

    grouped = {}
    for order in orders:
        key, name, code = _credit(order)
        row = grouped.get(key)
        if row is None:
            row = grouped[key] = {
                "name": name,
                "code": code,
                "orders": 0,
                "billed": ZERO,
                "received": ZERO,
                "outstanding": ZERO,
                "overdue_orders": 0,
            }
        billed = order.total_amount
        # order_paid sums in the database and comes back with the full
        # precision of the sum; money() puts it on paise like everything else
        paid = money(order_paid(order))
        balance = max(billed - paid, ZERO)

        row["orders"] += 1
        row["billed"] += billed
        # never count more than was billed: an overpayment is dealer credit,
        # not extra collection against this order
        row["received"] += min(paid, billed)
        row["outstanding"] += balance
        if balance > ZERO:
            row["overdue_orders"] += 1

    rows = []
    for row in grouped.values():
        # the number the report exists for: how much of what they sold has
        # actually come back
        row["collected_pc"] = (
            money(row["received"] * 100 / row["billed"]) if row["billed"] else ZERO
        )
        rows.append(row)

    rows.sort(key=lambda r: r["outstanding"], reverse=True)
    rows = [r for r in rows if match_row(r, filters["search"], "name", "code")]

    return TemplateResponse(request, "reports/sales_collection.html", _page(
        request, filters, slug="sales-collection", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "orders": sum(r["orders"] for r in rows),
                "billed": sum((r["billed"] for r in rows), ZERO),
                "received": sum((r["received"] for r in rows), ZERO),
                "outstanding": sum((r["outstanding"] for r in rows), ZERO),
                "overdue_orders": sum(r["overdue_orders"] for r in rows),
            },
        },
    ))


# ------------------------------------------------------------------ export




@login_required
def export(request, slug, fmt):
    """Download a report as CSV, Excel or PDF.

    The rows are not rebuilt here. This runs the report's own view, which
    hands back a TemplateResponse, and reads the context that page was about
    to render — so a download is exactly what is on screen, filters and all,
    and the two cannot drift apart.

    That also means the visibility rule is enforced once, in the report view,
    rather than a second time here where it could be forgotten.
    """
    card = next((c for c in REPORT_CARDS if c["slug"] == slug), None)
    writer = exports.WRITERS.get(fmt)
    if card is None or writer is None:
        raise Http404(f"No {fmt} export for report '{slug}'.")

    # The view is looked up from the card's own route rather than kept in a
    # second list here. A hand-kept table had to sit below every view it
    # named, so adding a report at the end of this file broke the import
    # with a NameError. This cannot fall out of step.
    view = resolve(reverse(card["url"])).func

    # the filters ride in on the query string, exactly as the page received them
    context = view(request).context_data
    columns, rows = exports.table_for(slug, context)

    # a line of provenance for the top of the file: which slice of time, and
    # whose orders, this download covers
    parts = [context["label"]]
    if context.get("search"):
        parts.append(f'search "{context["search"]}"')
    if not context["is_manager"]:
        parts.append("your orders only")
    subtitle = " · ".join(parts)

    return writer(context["card"], columns, rows, subtitle)


# ======================================================================
#  14. Sales Executive Visit Report  (attendance)
#
#  Who visited which dealer, when, where, and with what photo.
#
#  Not for dealers. Management sees every executive's visits; an executive
#  sees only their own. A dealer has no reason to read who called on whom,
#  so they are refused outright rather than shown an empty table.
# ======================================================================


@login_required
def visit_report(request):
    """Every visit in the period, newest first, numbered per dealer."""
    from attendance.models import Visit

    filters = read_filter(request)
    sales = _sales(request)
    manager = is_manager(request.user)

    # A dealer is not shown other people's movements — but a 404 debug page
    # is the wrong way to say so. Send them back to the report list with a
    # plain sentence, the same way Attendance turns them away.
    if sales is None and not manager:
        messages.info(
            request,
            "The visit report is for sales executives and management only.",
        )
        return redirect("reports:reports")

    visits = Visit.objects.select_related("dealer", "sales_executive")

    # an executive sees their own; management sees everyone and may narrow
    if sales is not None and not manager:
        visits = visits.filter(sales_executive=sales)
    elif manager:
        chosen = filters["sales_id"]
        if chosen and chosen.isdigit():
            visits = visits.filter(sales_executive_id=chosen)

    visits = apply_dates(visits, filters, "visited_on")

    dealer_id = filters["dealer_id"]
    if dealer_id and dealer_id.isdigit():
        visits = visits.filter(dealer_id=dealer_id)

    # latest visit first; the primary key tie-breaks two visits recorded in the
    # same moment, so the rows do not shuffle between requests
    rows = list(visits.order_by("-visited_on", "-pk"))

    term = filters["search"]
    if term:
        needle = term.lower()
        rows = [
            v for v in rows
            if needle in v.dealer.name.lower()
            or needle in v.sales_executive.name.lower()
            or needle in v.sales_executive.code.lower()
            or needle in (v.note or "").lower()
        ]

    # Number each visit to a dealer within the period: first visit, second
    # visit, and so on. Counted oldest-first so "1st" means the first of the
    # period, then the list is turned back round to show the newest on top.
    seen = {}
    for visit in sorted(rows, key=lambda v: (v.visited_on, v.created_at)):
        key = (visit.sales_executive_id, visit.dealer_id)
        seen[key] = seen.get(key, 0) + 1
        visit.visit_no = seen[key]

    dealers_seen = {v.dealer_id for v in rows}
    with_location = [v for v in rows if v.has_location]

    return TemplateResponse(request, "reports/visit_report.html", _page(
        request, filters, slug="visit-report", paginate="rows",
        extra={
            "rows": rows,
            "totals": {
                "visits": len(rows),
                "dealers": len(dealers_seen),
                "executives": len({v.sales_executive_id for v in rows}),
                "located": len(with_location),
                "days": len({v.visited_on for v in rows}),
            },
            # the first one with coordinates, for the map at the top
            "focus": with_location[0] if with_location else None,
        },
    ))
