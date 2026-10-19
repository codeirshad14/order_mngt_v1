from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from delaer.models import DealerProfile
from myorder.models import Order
from myorder.views import is_manager, is_sales

from .forms import PaymentForm
from .models import Payment, order_balance, order_paid

# Create your views here.

ZERO = Decimal("0.00")

# How many rows each of the two tables shows at a time. The order list, the
# product list and the reports all use the same number.
PER_PAGE = 100


def _billed(orders):
    """What a set of orders is worth in total.

    Order.total_amount is worked out from its lines, so this adds them up in
    Python. Order counts here are small; if that ever changes, swap this for
    a database aggregate.
    """
    return sum((o.total_amount for o in orders), ZERO)


def _received(payments):
    return payments.aggregate(total=Sum("amount"))["total"] or ZERO


@login_required
def payment(request):
    manager = is_manager(request.user)
    my_dealer = DealerProfile.objects.filter(user=request.user).first()

    # a salesman has no dealer profile but does have a book of business, so
    # they are let through the same way a manager is
    my_sales = is_sales(request.user)

    if my_dealer is None and not manager and not my_sales:
        messages.error(request, "Set up your dealer profile first.")
        return redirect("delaer:mydealer")

    # ---- who this page is about ----
    # a dealer only ever sees their own money; a manager sees everyone and can
    # narrow to one dealer
    dealer_id = request.GET.get("dealer", "")
    ledger_dealer = my_dealer
    if manager:
        ledger_dealer = DealerProfile.objects.filter(pk=dealer_id).first() if dealer_id.isdigit() else None

    # ---- record a payment ----
    open_modal = False

    if request.method == "POST":
        form = PaymentForm(request.POST, dealer=None if manager else my_dealer)
        if form.is_valid():
            saved = form.save()
            messages.success(
                request,
                f"Receipt {saved.receipt_no} recorded — {saved.amount} against {saved.against}.",
            )
            return redirect("payment:payment")
        messages.error(request, "Please correct the errors below.")
    else:
        # "Receive" on an outstanding row arrives as ?pay=<order id>: open the
        # modal with that order chosen and its balance already filled in
        initial = {}
        pay_id = request.GET.get("pay", "")
        if pay_id.isdigit():
            wanted = Order.objects.filter(pk=pay_id, status=Order.Status.FINAL).first()
            # a dealer may only pay their own orders
            if wanted and (manager or (my_dealer and wanted.dealer_id == my_dealer.pk)):
                initial = {
                    "dealer": wanted.dealer_id,
                    "order": wanted.pk,
                    "amount": order_balance(wanted),
                }
                open_modal = True

        form = PaymentForm(initial=initial, dealer=None if manager else my_dealer)

    # ---- the books ----
    orders = Order.objects.filter(status=Order.Status.FINAL).select_related("dealer")
    payments = Payment.objects.select_related("dealer", "order")

    if ledger_dealer:
        orders = orders.filter(dealer=ledger_dealer)
        payments = payments.filter(dealer=ledger_dealer)
    elif not manager:
        orders, payments = orders.none(), payments.none()

    # the totals above are for everything owed, so they are worked out before
    # the date filter narrows the payment list below
    billed = _billed(orders.prefetch_related("items"))
    received = _received(payments)
    outstanding = billed - received

    # money taken that is not tied to an order yet
    advance = _received(payments.filter(order__isnull=True))

    # ---- filters for the lists ----
    date_from = parse_date(request.GET.get("from", "") or "")
    date_to = parse_date(request.GET.get("to", "") or "")
    if date_from:
        payments = payments.filter(paid_on__gte=date_from)
    if date_to:
        payments = payments.filter(paid_on__lte=date_to)

    mode = request.GET.get("mode", "")
    if mode in Payment.Mode.values:
        payments = payments.filter(mode=mode)

    # The two panels search independently, so each has its own box: oq for the
    # outstanding list, pq for the receipts. One shared term would mean typing
    # in one panel silently rewrote the other.
    outstanding_search = request.GET.get("oq", "").strip()
    payment_search = request.GET.get("pq", "").strip()

    if payment_search:
        # matched in the database, before the list is cut to 30 below —
        # searching only what already fits on screen would find almost nothing
        match = (
            Q(receipt_no__icontains=payment_search)
            | Q(dealer__name__icontains=payment_search)
            | Q(order__order_no__icontains=payment_search)
            | Q(reference__icontains=payment_search)
            | Q(note__icontains=payment_search)
        )
        # "advance" is a state rather than a word in any column, so spell it out
        if "advance" in payment_search.lower():
            match |= Q(order__isnull=True)

        # Mode is stored as a code but shown as a label, so match the labels
        # and search by the codes behind them. Without this, searching for a
        # word that is plainly there in the Mode column — "cheque", or the
        # "RTGS" in "NEFT / RTGS" — found nothing.
        wanted = [
            value for value, label in Payment.Mode.choices
            if payment_search.lower() in label.lower()
        ]
        if wanted:
            match |= Q(mode__in=wanted)

        payments = payments.filter(match)

    # ---- order-by-order position ----
    rows = []
    # newest first. The primary key is the tie-break: several orders share an
    # ordered_on date, and without it those rows could swap places between
    # requests and shuffle across page boundaries
    for order in orders.prefetch_related("items", "payments").order_by("-ordered_on", "-pk"):
        rows.append({
            "order": order,
            "paid": order_paid(order),
            "balance": order_balance(order),
            "settled": order_balance(order) <= 0,
        })

    pending_rows = [r for r in rows if not r["settled"]]
    pending_total = len(pending_rows)

    if outstanding_search:
        # balance is worked out from the lines, not stored, so this list is
        # already in memory — match it here rather than in the database
        needle = outstanding_search.lower()
        pending_rows = [
            r for r in pending_rows
            if needle in r["order"].order_no.lower()
            or needle in r["order"].dealer.name.lower()
            or needle in ("part paid" if r["paid"] > 0 else "unpaid")
        ]

    # 100 rows a page in each table, the same size the order list, the product
    # list and the reports use. The four totals above are worked out over
    # everything that matched, so they keep describing the whole ledger rather
    # than the hundred rows on screen.
    #
    # The two tables page independently: outstanding on ?page, history on
    # ?hpage. Each pager's querystring drops its own page number and keeps the
    # other's, so paging one table does not send the other back to page one.
    pending_page = Paginator(pending_rows, PER_PAGE).get_page(
        request.GET.get("page"))
    payment_page = Paginator(payments, PER_PAGE).get_page(
        request.GET.get("hpage"))

    def _query(drop):
        params = request.GET.copy()
        params.pop(drop, None)
        return params.urlencode()

    return render(request, "payment/payment.html", {
        "form": form,
        "open_modal": open_modal,
        "is_manager": manager,
        "dealer": ledger_dealer or my_dealer,
        "dealers": DealerProfile.objects.all() if manager else None,
        "dealer_id": dealer_id,

        "billed": billed,
        "received": received,
        "outstanding": outstanding,
        "advance": advance,

        # "showing X of Y" in each toolbar, so a search that hides rows says so
        "pending_count": len(pending_rows),
        "pending_total": pending_total,
        "payment_count": payments.count(),

        "pending_rows": pending_page.object_list,
        "pending_page": pending_page,
        "pending_range": pending_page.paginator.get_elided_page_range(
            pending_page.number, on_each_side=1, on_ends=1),
        "pending_query": _query("page"),

        "payments": payment_page.object_list,
        "payment_page": payment_page,
        "payment_range": payment_page.paginator.get_elided_page_range(
            payment_page.number, on_each_side=1, on_ends=1),
        "payment_query": _query("hpage"),

        "date_from": request.GET.get("from", ""),
        "date_to": request.GET.get("to", ""),
        "mode": mode,
        "modes": Payment.Mode.choices,
        "outstanding_search": outstanding_search,
        "payment_search": payment_search,
    })
