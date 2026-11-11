
from django.urls import path

from . import views

app_name = "web"

urlpatterns = [

    # the whole site is one page; the nav links jump to sections on it
    path("", views.home, name="home"),

    # the "Download app" page the Get App buttons point to
    path("app/", views.install, name="install"),
    path("offline/", views.offline, name="offline"),

    # progressive web app: these two must sit at the site root, not /static/
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),

    # search engines
    path("robots.txt", views.robots_txt, name="robots"),
    path("sitemap.xml", views.sitemap_xml, name="sitemap"),
    path("favicon.ico", views.favicon, name="favicon"),

]
