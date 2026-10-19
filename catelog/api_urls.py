from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import api

app_name = "catelog_api"

# LoginRequiredMiddleware runs before the view, so it would redirect an API
# call to the login page before ApiKeyAuthentication ever saw the X-API-Key
# header. These views do their own auth, the same as the product API.
urlpatterns = [

    path("catelog/",
         login_not_required(api.CatelogListCreate.as_view()),
         name="catelog_list_create"),
    # <lookup> is the catelog's name
    path("catelog/<str:lookup>/",
         login_not_required(api.CatelogDetail.as_view()),
         name="catelog_detail"),

    path("newarrival/",
         login_not_required(api.NewArrivalListCreate.as_view()),
         name="newarrival_list_create"),
    path("newarrival/<str:lookup>/",
         login_not_required(api.NewArrivalDetail.as_view()),
         name="newarrival_detail"),

]
