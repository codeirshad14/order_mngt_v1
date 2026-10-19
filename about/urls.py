
from django.urls import path
from .import views

app_name = "about"

urlpatterns = [

    path("about", views.about, name="about"),
    path("upload", views.upload_image, name="upload"),

 
]

