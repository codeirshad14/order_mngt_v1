"""
URL configuration for order_mngt project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from mybase import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_not_required
from django.views.static import serve


urlpatterns = [
    path('admin/', admin.site.urls),
    # login / logout / password change, from django.contrib.auth
    path('accounts/', include('django.contrib.auth.urls')),
    path('mybase', views.mybase, name='mybase'),
    path("dashboard/", include("dashboard.urls")),
    path("products/", include("products.urls")),
    path("delaer/", include("delaer.urls")),
    path("myorder/", include("myorder.urls")),
    path("catelog/", include("catelog.urls")),
    path("contact/", include("contact.urls")),
    path("about/", include("about.urls")),
    path("bankdetails/", include("bankdetails.urls")),
    path("payment/", include("payment.urls")),
    path("reports/", include("reports.urls")),
    path("attendance/", include("attendance.urls")),

    # REST API for the mobile app and Tally — authenticated by X-API-Key
    path("api/", include("products.api_urls")),

    # the public one-page site — this is the landing page at /
    # it holds only path(""), so it matches / exactly and shadows nothing above
    path("", include("web.urls")),

]
if settings.DEBUG:
    # LoginRequiredMiddleware guards every view, and in DEBUG the media files
    # are served by a view too — so without this the logo and the product
    # photos on the public landing page redirect a visitor to the login form
    # and show up broken. login_not_required lets them through.
    urlpatterns += static(
        settings.MEDIA_URL,
        view=login_not_required(serve),
        document_root=settings.MEDIA_ROOT,
    )