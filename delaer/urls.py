
from django.urls import path
from .import views

app_name = "delaer"

urlpatterns = [

    path("mydealer", views.mydealer, name="mydealer"),

 
]

