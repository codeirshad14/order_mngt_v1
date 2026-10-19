from django.shortcuts import render

from .models import BankDetail

# Create your views here.
def bankdetails(request):

    return render(request, "bankdetails/bankdetails.html", {
        "accounts": BankDetail.objects.all(),
    })
