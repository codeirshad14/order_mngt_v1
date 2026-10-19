
from django.urls import path
from .import views

app_name = "products"

urlpatterns = [

    path("products", views.products, name="products"),
    # JSON for the topbar search box, on every page
    path("suggest", views.suggest, name="suggest"),
    # csv | excel | pdf — must sit above <int:pk> is not needed here, the
    # int converter can't match these words, but keep them grouped
    path("export/<str:fmt>", views.export, name="export"),
    # the one product details page — every module links here, none repeats it
    path("<int:pk>/", views.detail, name="detail"),

 
]

