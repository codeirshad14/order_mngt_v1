"""Shared plumbing for every report.

One place decides what a period, a date range, a dealer filter and a search
term mean. All eight reports call these, so they answer the same question the
same way and can share a single toolbar template.

Nothing here writes: reports only ever read.
"""

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone
from django.utils.dateparse import parse_date

from myorder.models import Order

# The order list already decides who may see whose orders. Reports reuse that
# exact function rather than repeating the rule — a report must never widen
# what a dealer can see.
from myorder.views import (  # noqa: F401  (re-exported for the reports)
    _company,
    _sales,
    _same_state,
    _visible_orders,
    is_manager,
)

# ---------------------------------------------------------------- periods

PERIOD_ALL = "all"
PERIOD_MONTH = "month"
PERIOD_YEAR = "year"
PERIOD_RANGE = "range"

# value -> label, in the order the segment shows them
PERIODS = [
    (PERIOD_ALL, "All time"),
    (PERIOD_MONTH, "Monthly"),
    (PERIOD_YEAR, "Yearly"),
    (PERIOD_RANGE, "Custom range"),
]

PAISE = Decimal("0.01")


def money(value):
    """Any amount, at two decimals — the only way a report prints money.

    The reports add money up from OrderItem.line_net / line_gst, which are
    already on paise, so this is a guard rather than a workhorse: it catches
    anything divided or averaged on the way to the page, such as the weighted
    average rate in the item summary.
    """
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(PAISE, rounding=ROUND_HALF_UP)


def _month_bounds(stamp):
    """First and last day of the month `stamp` falls in."""
    first = stamp.replace(day=1)
    # jump to the 1st of next month, then step back a day — avoids having to
    # know which months have 30, 31 or 28/29 days
    following = (first.replace(year=first.year + 1, month=1)
                 if first.month == 12
                 else first.replace(month=first.month + 1))
    return first, following - timedelta(days=1)


def read_filter(request):
    """Everything the toolbar sent, normalised into one dictionary.

    Always returns every key, so a template never has to guard against a
    missing one. `date_from` / `date_to` are the only values the queries use;
    the rest are there so the toolbar can redraw itself.
    """
    today = timezone.localdate()

    period = request.GET.get("period", PERIOD_ALL)
    if period not in dict(PERIODS):
        period = PERIOD_ALL

    # the month picker sends "YYYY-MM"; the year picker sends "YYYY"
    month = request.GET.get("month", today.strftime("%Y-%m"))
    year = request.GET.get("year", str(today.year))

    date_from = date_to = None
    label = "All time"

    if period == PERIOD_MONTH:
        try:
            stamp = date(int(month[:4]), int(month[5:7]), 1)
        except (ValueError, IndexError):
            # an unparseable month falls back to this one rather than erroring
            stamp = today.replace(day=1)
            month = today.strftime("%Y-%m")
        date_from, date_to = _month_bounds(stamp)
        label = stamp.strftime("%B %Y")

    elif period == PERIOD_YEAR:
        try:
            number = int(year)
        except ValueError:
            number = today.year
            year = str(number)
        date_from, date_to = date(number, 1, 1), date(number, 12, 31)
        label = str(number)

    elif period == PERIOD_RANGE:
        # either end may be left blank — an open-ended range is still useful
        date_from = parse_date(request.GET.get("from", "") or "")
        date_to = parse_date(request.GET.get("to", "") or "")
        if date_from and date_to:
            label = f"{date_from:%d %b %Y} – {date_to:%d %b %Y}"
        elif date_from:
            label = f"From {date_from:%d %b %Y}"
        elif date_to:
            label = f"Up to {date_to:%d %b %Y}"
        else:
            label = "All time"

    # what the period links must carry along, so switching from Monthly to
    # Yearly does not quietly drop the search term or the chosen dealer
    keep = request.GET.copy()
    for key in ("period", "month", "year", "from", "to"):
        keep.pop(key, None)

    return {
        "keep": keep.urlencode(),
        "period": period,
        "periods": PERIODS,
        "month": month,
        "year": year,
        "date_from": date_from,
        "date_to": date_to,
        # the raw strings, so the two date boxes redraw with what was typed
        "from_value": request.GET.get("from", ""),
        "to_value": request.GET.get("to", ""),
        "search": request.GET.get("q", "").strip(),
        "dealer_id": request.GET.get("dealer", ""),
        # "direct" means the orders a dealer placed with no salesman on them
        "sales_id": request.GET.get("sales", ""),
        "label": label,
        # every filter as it came in, for the export links and page links
        "query": request.GET.urlencode(),
    }


def period_params(filters):
    """The period half of the filter, as a dict for a drill-down link.

    A link from one report into another must land on the same stretch of
    time, or the figures stop adding up against the page it came from.
    """
    period = filters["period"]
    carry = {"period": period}

    if period == PERIOD_MONTH:
        carry["month"] = filters["month"]
    elif period == PERIOD_YEAR:
        carry["year"] = filters["year"]
    elif period == PERIOD_RANGE:
        if filters["from_value"]:
            carry["from"] = filters["from_value"]
        if filters["to_value"]:
            carry["to"] = filters["to_value"]

    return carry


def apply_dates(queryset, filters, field):
    """Narrow `queryset` to the chosen period, on whichever date field the
    model calls its own (`ordered_on`, `paid_on`, …)."""
    if filters["date_from"]:
        queryset = queryset.filter(**{f"{field}__gte": filters["date_from"]})
    if filters["date_to"]:
        queryset = queryset.filter(**{f"{field}__lte": filters["date_to"]})
    return queryset


def report_orders(request, filters, statuses=None):
    """The orders a report works from: what this user may see, narrowed to the
    period, the chosen dealer and — usually — to placed orders only.

    `statuses=None` means final orders only, which is what a report normally
    wants: a draft is still being edited and is not business that happened.
    Pass an explicit list to include drafts and held orders.
    """
    orders = _visible_orders(request)

    if statuses is None:
        statuses = [Order.Status.FINAL]
    if statuses:
        orders = orders.filter(status__in=statuses)

    orders = apply_dates(orders, filters, "ordered_on")

    # Narrow to one dealer, and to one salesman or the orders nobody is
    # credited with.
    #
    # Open to everyone, not just managers. These only ever *reduce* what
    # _visible_orders already allowed — they cannot widen it — and the
    # drill-down links depend on them: a salesman clicking a dealer in the
    # "wise Dealer" report has to land on that dealer's orders, not on all
    # of their own. The pickers in the toolbar stay manager-only, because a
    # salesman has nobody else to pick.
    dealer_id = filters["dealer_id"]
    if dealer_id and dealer_id.isdigit():
        orders = orders.filter(dealer_id=dealer_id)

    sales_id = filters["sales_id"]
    if sales_id == "direct":
        orders = orders.filter(sales_executive__isnull=True)
    elif sales_id and sales_id.isdigit():
        orders = orders.filter(sales_executive_id=sales_id)

    return orders


def search_orders(orders, term):
    """Free-text match over the fields someone would recognise an order by.

    Applied in Python rather than SQL because several reports have already
    turned the queryset into rows by this point, and a report's volumes are
    small enough that it makes no difference.
    """
    if not term:
        return orders
    needle = term.lower()
    return [
        order for order in orders
        if needle in order.order_no.lower()
        or needle in order.dealer.name.lower()
        or needle in order.get_status_display().lower()
    ]


def match_row(row, term, *fields):
    """Does this report row match the search box? `fields` are dict keys."""
    if not term:
        return True
    needle = term.lower()
    return any(needle in str(row.get(f, "")).lower() for f in fields)


def order_items(request, filters):
    """Every order line inside the report's period, as a queryset.

    Grouped and totalled in Python by the reports that use it, from the
    model's own per-line properties — see _item_totals() for why.
    """
    from myorder.models import OrderItem

    lines = OrderItem.objects.filter(
        order__in=report_orders(request, filters)
    ).select_related("product", "product__brand", "product__unit", "order", "order__dealer")

    return lines
