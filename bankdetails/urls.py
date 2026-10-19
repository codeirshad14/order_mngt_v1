
from django.urls import path
from .import views

app_name = "bankdetails"

urlpatterns = [

    path("bankdetails", views.bankdetails, name="bankdetails"),

 
]

