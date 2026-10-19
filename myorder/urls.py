
from django.urls import path
from .import views

app_name = "myorder"

urlpatterns = [

    path("myorder", views.myorder, name="myorder"),
    path("export/<str:fmt>", views.export_orders, name="export"),
    path("shop", views.catalogue, name="catalogue"),
    path("add/<int:product_pk>", views.add_to_cart, name="add_to_cart"),
    path("cart", views.cart, name="cart"),
    path("<int:pk>/", views.edit, name="edit"),
    path("<int:pk>/remove/<int:item_pk>", views.remove_item, name="remove_item"),
    path("<int:pk>/hold", views.hold, name="hold"),
    path("<int:pk>/resume", views.resume, name="resume"),
    path("<int:pk>/finalise", views.finalise, name="finalise"),
    path("<int:pk>/print", views.print_order, name="print"),

]
