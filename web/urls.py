
from django.urls import path

from . import views

app_name = "web"

urlpatterns = [

    # the whole site is one page; the nav links jump to sections on it
    path("", views.home, name="home"),

]
