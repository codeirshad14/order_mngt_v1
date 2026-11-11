"""SEO tags and app-install data for the public site.

Everything a search engine, a social share or a phone reads about the site is
built here from what the admin already holds (Contact, About, Product), so it
never goes stale. The views in web/views.py only hand it to the templates.
"""

import json

from django.templatetags.static import static
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.text import Truncator

from about.models import About
from contact.models import Contact
from products.models import Product

# The one address the site is known by. Canonical links, the sitemap and the
# share cards all use it, whichever host name (www or not) the visitor typed.
SITE_URL = "https://order.initiatorsolutions.com"

# Bump this when sw.js or the files it pre-caches change, so installed apps
# throw away their old copies.
SW_VERSION = "2"

DEFAULT_NAME = "Order Mgmt"

# the app's own colours: --primary-600 for the title bar, --bg for the splash
THEME_COLOR = "#5145cd"
BACKGROUND_COLOR = "#f6f7fb"

# 1200 x 630, the size WhatsApp, Facebook and LinkedIn want for a share card
SHARE_IMAGE = "assets/pwa/og-image.png"


def get_company():
    """The head office, or any office if none is marked as head office."""
    return Contact.objects.filter(is_primary=True).first() or Contact.objects.first()


def company_name(company):
    return company.name if company else DEFAULT_NAME


def short_name(company):
    """The label under the icon on a phone — about 12 letters fit."""
    name = company_name(company)
    return name if len(name) <= 12 else name.split()[0][:12]


def absolute(url):
    """'/media/x.png' -> 'https://order.initiatorsolutions.com/media/x.png'."""
    if url.startswith(("http://", "https://")):
        return url
    return SITE_URL + (url if url.startswith("/") else "/" + url)


def to_json_ld(data):
    """JSON for a <script type="application/ld+json"> tag.

    "</" is escaped so a product name can never close the script tag early.
    """
    return json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")


# ---------------------------------------------------------------- structured data

def organization(company):
    """schema.org Organization: who runs the site, for Google's knowledge panel."""
    data = {
        "@type": "Organization",
        "@id": SITE_URL + "/#organization",
        "name": company_name(company),
        "url": SITE_URL + "/",
        "logo": absolute(company.logo.url if company and company.logo else static("assets/pwa/icon-512.png")),
    }
    if not company:
        return data

    phone = company.phone or company.mobile
    if company.email:
        data["email"] = company.email
    if phone:
        data["telephone"] = phone
    data["address"] = {
        "@type": "PostalAddress",
        "streetAddress": ", ".join(company.address_lines),
        "addressLocality": company.city,
        "addressRegion": company.state,
        "postalCode": company.pincode,
        "addressCountry": "IN",
    }
    data["contactPoint"] = {
        "@type": "ContactPoint",
        "contactType": "sales",
        "telephone": phone,
        "email": company.email,
        "areaServed": "IN",
        "availableLanguage": ["en", "hi"],
    }
    same_as = [url for _label, _icon, url in company.socials]
    if company.website:
        same_as.append(company.website)
    if same_as:
        data["sameAs"] = same_as
    return data


def web_app(company):
    """schema.org WebApplication: the installable app itself."""
    return {
        "@type": "WebApplication",
        "@id": SITE_URL + "/#app",
        "name": f"{company_name(company)} Dealer App",
        "url": SITE_URL + "/",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Android, iOS, Windows, macOS",
        "browserRequirements": "Requires a modern web browser",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "INR"},
        "publisher": {"@id": SITE_URL + "/#organization"},
    }


def product_list(products):
    """schema.org ItemList of the products shown on the landing page."""
    items = []
    for position, product in enumerate(products, start=1):
        items.append({
            "@type": "ListItem",
            "position": position,
            "item": {
                "@type": "Product",
                "name": product.name,
                "sku": product.partno,
                "image": absolute(product.front_url),
                "brand": {"@type": "Brand", "name": str(product.brand)},
                "offers": {
                    "@type": "Offer",
                    "price": str(product.price_including_gst),
                    "priceCurrency": "INR",
                    "availability": "https://schema.org/InStock",
                    "url": SITE_URL + "/#products",
                },
            },
        })
    return {"@type": "ItemList", "name": "Products", "itemListElement": items}


# ---------------------------------------------------------------- page tags

def home_seo(company, about, products, stats):
    """Title, description, share card and structured data for the landing page."""
    name = company_name(company)
    city = company.city if company and company.city else ""

    if about and about.description:
        intro = Truncator(strip_tags(about.description)).words(18)
    else:
        intro = (
            f"{name}{' in ' + city if city else ''} – order online from "
            f"{stats['products']} products across {stats['brands']} brands."
        )
    description = Truncator(
        f"{intro} Live stock, GST-ready prices, invoices and payments in one "
        f"dealer app. Install free on Android, iPhone or PC."
    ).chars(160)

    return {
        "title": f"{name} | Dealer Ordering App – Order Online 24×7",
        "description": description,
        "url": SITE_URL + "/",
        "image": absolute(static(SHARE_IMAGE)),
        "site_name": name,
        "json_ld": to_json_ld({
            "@context": "https://schema.org",
            "@graph": [
                organization(company),
                {
                    "@type": "WebSite",
                    "@id": SITE_URL + "/#website",
                    "url": SITE_URL + "/",
                    "name": name,
                    "inLanguage": "en-IN",
                    "publisher": {"@id": SITE_URL + "/#organization"},
                },
                web_app(company),
                product_list(products),
            ],
        }),
    }


# ---------------------------------------------------------------- app manifest

def manifest(company):
    """The web app manifest: what a phone needs to install the site as an app."""
    name = company_name(company)
    icon_192 = static("assets/pwa/icon-192.png")
    return {
        "id": "/",
        "name": f"{name} – Dealer Orders",
        "short_name": short_name(company),
        "description": f"Order from {name}: live stock, GST prices, invoices and payments.",
        "lang": "en-IN",
        "dir": "ltr",
        # signed-out users land on the login form first, then come straight here
        "start_url": reverse("dashboard:dashboard"),
        "scope": "/",
        "display": "standalone",
        "display_override": ["standalone", "minimal-ui"],
        "orientation": "any",
        "theme_color": THEME_COLOR,
        "background_color": BACKGROUND_COLOR,
        "categories": ["business", "shopping", "productivity"],
        "prefer_related_applications": False,
        "icons": [
            {"src": icon_192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": static("assets/pwa/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": static("assets/pwa/icon-maskable-192.png"), "sizes": "192x192", "type": "image/png",
             "purpose": "maskable"},
            {"src": static("assets/pwa/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png",
             "purpose": "maskable"},
        ],
        # long-press the app icon on Android / right-click it on desktop
        "shortcuts": [
            {"name": "Place an order", "short_name": "New order",
             "url": reverse("myorder:catalogue"), "icons": [{"src": icon_192, "sizes": "192x192"}]},
            {"name": "My orders", "short_name": "Orders",
             "url": reverse("myorder:myorder"), "icons": [{"src": icon_192, "sizes": "192x192"}]},
            {"name": "Payments", "short_name": "Payments",
             "url": reverse("payment:payment"), "icons": [{"src": icon_192, "sizes": "192x192"}]},
            {"name": "Products", "short_name": "Products",
             "url": reverse("products:products"), "icons": [{"src": icon_192, "sizes": "192x192"}]},
        ],
    }


def sitemap_pages():
    """The public pages search engines should list, with when each last changed."""
    # the landing page shows products, contact details and the About text, so
    # it changed whenever the newest of those did
    changed = [
        obj.updated_at
        for obj in (
            Product.objects.order_by("-updated_at").first(),
            Contact.objects.order_by("-updated_at").first(),
            About.objects.order_by("-updated_at").first(),
        )
        if obj is not None
    ]
    home_changed = max(changed) if changed else None

    return [
        {"loc": SITE_URL + "/", "lastmod": home_changed, "changefreq": "daily", "priority": "1.0"},
    ]
