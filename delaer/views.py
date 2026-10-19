from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import DealerProfileForm
from .models import DealerProfile

# Create your views here.


@login_required
def mydealer(request):
    """One company profile per user — the same page creates and edits it."""
    profile = DealerProfile.objects.filter(user=request.user).first()

    if request.method == "POST":
        form = DealerProfileForm(request.POST, instance=profile)
        if form.is_valid():
            saved = form.save(commit=False)
            saved.user = request.user          # never taken from the form
            saved.save()
            messages.success(request, "Dealer profile saved.")
            return redirect("delaer:mydealer")
        messages.error(request, "Please correct the errors below.")
    else:
        form = DealerProfileForm(instance=profile)

    return render(request, "delaer/dealer.html", {
        "form": form,
        "profile": profile,
    })
