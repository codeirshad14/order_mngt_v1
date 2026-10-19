from django.contrib.auth.decorators import login_not_required
from django.urls import path

from . import api

app_name = "reports_api"

# LoginRequiredMiddleware runs before the view, so it would redirect an API
# call to the login page before ApiKeyAuthentication ever saw the X-API-Key
# header. These views do their own auth, the same as the product API.
urlpatterns = [

    path("reports/",
         login_not_required(api.ReportList.as_view()),
         name="list"),
    # <slug> is a report's slug, as the list above gives it
    path("reports/<slug:slug>/",
         login_not_required(api.ReportDetail.as_view()),
         name="detail"),

]
