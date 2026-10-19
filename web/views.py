"""The public website — one page, no login needed.

Everything on it is read from what the business already keeps in the admin:
the company details from Contact, the story from About, and real products
from the catalogue. Nothing here is written by hand into a template, so the
site keeps itself current.
"""

from django.contrib.auth.decorators import login_not_required
from django.shortcuts import render

from about.models import About
from catelog.models import Catelog
from contact.models import Contact
from products.models import Product

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

    return render(request, "web/index.html", {
        "company": company,
        "about": about,
        "products": products,
        "catelogs": Catelog.objects.prefetch_related("products")[:4],
        # a few honest numbers for the hero strip
        "stats": {
            "products": Product.objects.filter(is_active=True).count(),
            "brands": Product.objects.values("brand").distinct().count(),
            "catelogs": Catelog.objects.count(),
        },
    })
