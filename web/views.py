"""The public website — one page, no login needed.

Everything on it is read from what the business already keeps in the admin:
the company details from Contact, the story from About, and real products
from the catalogue. Nothing here is written by hand into a template, so the
site keeps itself current.
"""

from django.contrib.auth.decorators import login_not_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.views.decorators.cache import cache_control

from about.models import About
from catelog.models import Catelog
from contact.models import Contact
from products.models import Product

from . import services

# how many products the landing page shows before pointing at the catalogue
SHOWCASE = 8


@login_not_required
def home(request):
    """The single page: hero, about, products, contact.

    LoginRequiredMiddleware guards the whole project, so a public page has
    to say plainly that it is public — without this the site would bounce
    every visitor to the login form.
    """
    company = Contact.objects.filter(is_primary=True).first() or Contact.objects.first()
    about = About.objects.filter(is_active=True).first()

    # the things worth showing a visitor: in stock, and with a photo if we
    # have one, newest first
    products = (
        Product.objects.select_related("brand", "unit")
        .filter(is_active=True, stock__gt=0)
        .order_by("-created_at")[:SHOWCASE]
    )

    # a few honest numbers for the hero strip
    stats = {
        "products": Product.objects.filter(is_active=True).count(),
        "brands": Product.objects.values("brand").distinct().count(),
        "catelogs": Catelog.objects.count(),
    }

    return render(request, "web/index.html", {
        "company": company,
        "about": about,
        "products": products,
        "catelogs": Catelog.objects.prefetch_related("products")[:4],
        "stats": stats,
        # title, description, share card and structured data for search engines
        "seo": services.home_seo(company, about, products, stats),
    })


# The "Download app" page: an Install button plus the steps for each phone.
@login_not_required
def install(request):
    company = services.get_company()
    return render(request, "web/install.html", {
        "company": company,
        "seo": services.install_seo(company),
    })


# Shown by the installed app when a page is opened with no internet.
@login_not_required
def offline(request):
    return render(request, "web/offline.html")


# The web app manifest: name, icons and colours a phone uses to install the site.
@login_not_required
@cache_control(max_age=3600)
def manifest(request):
    return JsonResponse(
        services.manifest(services.get_company()),
        content_type="application/manifest+json",
        json_dumps_params={"ensure_ascii": False, "indent": 1},
    )


# The service worker. It has to be served from the site root, not /static/,
# so it may look after every page; no-cache so an update reaches phones at once.
@login_not_required
@cache_control(no_cache=True, max_age=0)
def service_worker(request):
    script = render_to_string("web/sw.js", {"version": services.SW_VERSION})
    response = HttpResponse(script, content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    return response


# robots.txt: what search engines may crawl, and where the sitemap is.
@login_not_required
def robots_txt(request):
    text = render_to_string("web/robots.txt", {"site_url": services.SITE_URL})
    return HttpResponse(text, content_type="text/plain")


# sitemap.xml: the public pages search engines should list.
@login_not_required
def sitemap_xml(request):
    xml = render_to_string("web/sitemap.xml", {"pages": services.sitemap_pages()})
    return HttpResponse(xml, content_type="application/xml")


# /favicon.ico: browsers and Google ask for it at the root, whatever the page says.
@login_not_required
def favicon(request):
    return redirect(static("assets/pwa/favicon.ico"), permanent=True)
