from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from delaer.models import DealerProfile
from myorder.models import Order, OrderItem
from myorder.views import is_manager
from products.models import Product

# Create your views here.

MONEY = DecimalField(max_digits=14, decimal_places=2)

# Line-value expressions, so totals are summed by the database rather than by
# walking every order in Python. These are functions, not constants: Django
# resolves an expression in place, so reusing one instance across two queries
# makes the second one fail with "is an aggregate".
def line_net():
    return ExpressionWrapper(F("rate") * F("qty"), output_field=MONEY)


def line_gst():
    return ExpressionWrapper(F("rate") * F("qty") * F("gst") / 100, output_field=MONEY)

RANGES = {
    "today": ("Today", 0),
    "7d": ("Last 7 days", 6),
    "30d": ("Last 30 days", 29),
    "90d": ("Last 90 days", 89),
}


def _money(value):
    return (value or Decimal("0")).quantize(Decimal("0.01"))


def _totals(orders):
    """Net, GST and gross for a set of orders, in one query."""
    # the aliases must not be named after a field the expressions use: an
    # alias shadows the column, and F("qty") would then resolve to Sum("qty")
    row = OrderItem.objects.filter(order__in=orders).aggregate(
        net=Sum(line_net()), gst=Sum(line_gst()), units=Sum("qty")
    )
    net, gst = _money(row["net"]), _money(row["gst"])
    return {"net": net, "gst": gst, "gross": net + gst, "qty": row["units"] or 0}


def _delta(now, before):
    """Percentage change, or None when there is nothing to compare against."""
    if not before:
        return None
    return round((now - before) / before * 100)


@login_required
def dashboard(request):
    manager = is_manager(request.user)
    my_dealer = DealerProfile.objects.filter(user=request.user).first()

    # ---- scope: a dealer sees only their own orders ----
    orders = Order.objects.select_related("dealer")
    if not manager:
        orders = orders.filter(dealer=my_dealer) if my_dealer else orders.none()

    # ---- filters ----
    today = timezone.localdate()
    preset = request.GET.get("range", "30d")
    date_from = parse_date(request.GET.get("from", "") or "")
    date_to = parse_date(request.GET.get("to", "") or "")

    if date_from or date_to:
        preset = "custom"
    else:
        days = RANGES.get(preset, RANGES["30d"])[1]
        date_from, date_to = today - timedelta(days=days), today

    period = orders
    if date_from:
        period = period.filter(ordered_on__gte=date_from)
    if date_to:
        period = period.filter(ordered_on__lte=date_to)

    dealer_id = request.GET.get("dealer", "")
    if manager and dealer_id.isdigit():
        period = period.filter(dealer_id=dealer_id)

    status = request.GET.get("status", "")
    scoped = period.filter(status=status) if status in Order.Status.values else period

    # ---- headline numbers, and the same window immediately before it ----
    placed = scoped.filter(status=Order.Status.FINAL)
    totals = _totals(placed)

    span = (date_to - date_from).days + 1 if date_from and date_to else 30
    prev = orders.filter(
        ordered_on__gte=date_from - timedelta(days=span),
        ordered_on__lt=date_from,
        status=Order.Status.FINAL,
    )
    prev_totals = _totals(prev)

    open_orders = scoped.exclude(status=Order.Status.FINAL)

    # ---- orders per day, for the bar chart ----
    # counted in two queries: all orders, and the placed ones, so each bar can
    # show how much of that day actually converted
    per_day = {
        row["ordered_on"]: row["n"]
        for row in scoped.values("ordered_on").annotate(n=Count("id"))
    }
    placed_per_day = {
        row["ordered_on"]: row["n"]
        for row in placed.values("ordered_on").annotate(n=Count("id"))
    }
    value_per_day = {
        row["order__ordered_on"]: _money(row["v"])
        for row in OrderItem.objects.filter(order__in=placed)
        .values("order__ordered_on")
        .annotate(v=Sum(line_net()) + Sum(line_gst()))
    }

    chart_days = min((date_to - date_from).days + 1, 31) if date_from and date_to else 30
    days = [date_to - timedelta(days=i) for i in range(chart_days - 1, -1, -1)]
    peak = max(per_day.values(), default=0) or 1

    # a date under every bar is unreadable past a week, so label a few
    step = max(1, round(len(days) / 6))

    chart = []
    for i, d in enumerate(days):
        total = per_day.get(d, 0)
        done = placed_per_day.get(d, 0)
        chart.append({
            "day": d,
            "count": total,
            "placed": done,
            "open": total - done,
            # height of each point as a share of the tallest day
            "pct_total": round(total / peak * 100),
            "pct_placed": round(done / peak * 100),
            "value": value_per_day.get(d, Decimal("0.00")),
            "is_today": d == today,
            "label": d.strftime("%d %b") if i % step == 0 or i == len(days) - 1 else "",
        })

    busiest = max(chart, key=lambda c: c["count"]) if chart else None
    daily_avg = round(sum(c["count"] for c in chart) / len(chart), 1) if chart else 0
    avg_pct = round(daily_avg / peak * 100)

    # ---- line geometry ----
    # x runs 0-100 across the range and y is inverted (SVG counts downward),
    # so the SVG can stretch to any width while the CSS fixes its height
    last = len(chart) - 1
    for i, point in enumerate(chart):
        point["x"] = round(i / last * 100, 3) if last else 50.0
        point["y_total"] = round(100 - point["count"] / peak * 100, 3)
        point["y_placed"] = round(100 - point["placed"] / peak * 100, 3)

    def polyline(key):
        return " ".join(f"{p['x']},{p[key]}" for p in chart)

    line_total = polyline("y_total")
    line_placed = polyline("y_placed")
    # the filled area is the total line closed down to the baseline
    area_total = (
        f"M0,100 L{line_total.replace(' ', ' L')} L100,100 Z" if chart else ""
    )

    # ---- what is selling ----
    top_products = (
        OrderItem.objects.filter(order__in=placed)
        .values("product__name", "product__partno")
        .annotate(units=Sum("qty"), value=Sum(line_net()))
        .order_by("-value")[:6]
    )

    top_dealers = (
        OrderItem.objects.filter(order__in=placed)
        .values("order__dealer__name")
        .annotate(value=Sum(line_net()), orders=Count("order", distinct=True))
        .order_by("-value")[:6]
        if manager else None
    )

    # ---- stock health, straight from the products module ----
    products = Product.objects.all()
    low = products.filter(stock__gt=0, stock__lte=Product.LOW_STOCK_AT)

    return render(request, "dashboard/dashboard.html", {
        "is_manager": manager,
        "dealer": my_dealer,
        "dealers": DealerProfile.objects.all() if manager else None,

        # filter state
        "preset": preset,
        "ranges": RANGES,
        "date_from": date_from.isoformat() if date_from else "",
        "date_to": date_to.isoformat() if date_to else "",
        "dealer_id": dealer_id,
        "status": status,
        "statuses": Order.Status.choices,

        # headline
        "order_count": placed.count(),
        "order_delta": _delta(placed.count(), prev.count()),
        "revenue": totals["gross"],
        "revenue_delta": _delta(totals["gross"], prev_totals["gross"]),
        "units": totals["qty"],
        "net": totals["net"],
        "gst": totals["gst"],
        "avg_order": _money(totals["gross"] / placed.count()) if placed.count() else Decimal("0.00"),

        # working state
        "draft_count": scoped.filter(status=Order.Status.DRAFT).count(),
        "hold_count": scoped.filter(status=Order.Status.HOLD).count(),
        "open_value": _totals(open_orders)["gross"],

        "chart": chart,
        "line_total": line_total,
        "line_placed": line_placed,
        "area_total": area_total,
        "chart_peak": peak,
        "chart_half": round(peak / 2, 1) if peak > 1 else peak,
        "busiest": busiest,
        "daily_avg": daily_avg,
        "avg_pct": avg_pct,
        "top_products": top_products,
        "top_dealers": top_dealers,
        "recent": scoped.order_by("-created_at")[:8],

        # stock
        "product_count": products.count(),
        "low_stock": low.order_by("stock")[:6],
        "low_count": low.count(),
        "out_count": products.filter(stock=0).count(),
    })
