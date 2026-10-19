from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import api

app_name = "products_api"

# LoginRequiredMiddleware runs before the view, so it would redirect an
# API call to the login page before ApiKeyAuthentication ever sees the
# X-API-Key header. These views do their own auth.
urlpatterns = [
    path("products/", login_not_required(api.ProductListCreate.as_view()), name="list_create"),
    # <lookup> is a product name, or its id — see ProductDetail.get_object
    path("products/<str:lookup>/", login_not_required(api.ProductDetail.as_view()), name="detail"),
]
