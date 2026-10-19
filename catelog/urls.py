
from django.urls import path
from .import views

app_name = "catelog"

urlpatterns = [

    path("catelog", views.catelog, name="catelog"),
    path("new", views.new_arrival, name="new_arrival"),
    path("<int:pk>/", views.detail, name="detail"),
]



