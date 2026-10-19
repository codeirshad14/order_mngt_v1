"""Marking a visit, and looking at the ones already marked.

Who may do what:

* a sales executive marks visits and sees their own;
* management sees everyone's but marks none — they are not in the field;
* a dealer has no business here at all and is turned away.

The report lives in the reports app with the others; this page is just the
act of marking one.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from delaer.models import SalesExecutive
from myorder.views import _sales, is_manager

from .forms import VisitForm
from .models import Visit

# how many of the executive's own visits the page lists underneath the form
RECENT = 12


@login_required
def attendance(request):
    """Mark a visit, and show the last few already marked."""
    sales = _sales(request)
    manager = is_manager(request.user)

    # a dealer has nothing to do here
    if sales is None and not manager:
        messages.error(request, "Only a sales executive can mark a visit.")
        return redirect("dashboard:dashboard")

    if request.method == "POST":
        # management can read this page but not mark a visit on it: they are
        # not the one standing at the dealer's door
        if sales is None:
            messages.error(request, "Only a sales executive can mark a visit.")
            return redirect("attendance:attendance")

        form = VisitForm(request.POST, request.FILES)
        if form.is_valid():
            visit = form.save(commit=False)
            # taken from the session, never from the form — nobody marks a
            # visit in somebody else's name
            visit.sales_executive = sales
            visit.save()

            where = visit.coordinates or "no location"
            messages.success(
                request,
                f"Visit to {visit.dealer.name} recorded ({where}).",
            )
            # redirect after POST, so a refresh cannot file the visit twice
            return redirect("attendance:attendance")

        messages.error(request, "Please correct the errors below.")
    else:
        form = VisitForm()

    # a manager reads everyone's; an executive reads their own
    visits = Visit.objects.select_related("dealer", "sales_executive")
    if sales is not None:
        visits = visits.filter(sales_executive=sales)

    return render(request, "attendance/attendance.html", {
        "form": form,
        "sales": sales,
        "is_manager": manager,
        "can_mark": sales is not None,
        "visits": visits[:RECENT],
        "visit_count": visits.count(),
        "executives": SalesExecutive.objects.filter(is_active=True) if manager else None,
    })
