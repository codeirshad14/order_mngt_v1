import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from contact.models import Contact

from . import services


class PublicPagesTests(TestCase):
    """The landing page and the install page are open to everyone and carry
    full search and share tags."""

    def setUp(self):
        Contact.objects.create(
            name="Acme Traders", is_primary=True, address="12 Market Road",
            city="Noida", state="Uttar Pradesh", phone="9999999999",
        )

    def test_home_has_seo_tags(self):
        response = self.client.get(reverse("web:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<link rel="canonical" href="https://order.initiatorsolutions.com/">')
        self.assertContains(response, 'property="og:image"')
        self.assertContains(response, "application/ld+json")
        self.assertContains(response, "Acme Traders | Dealer Ordering App")

    def test_home_has_get_app_button_and_manifest(self):
        response = self.client.get(reverse("web:home"))
        self.assertContains(response, "data-pwa-install")
        self.assertContains(response, 'rel="manifest"')

    def test_install_page_is_public(self):
        response = self.client.get(reverse("web:install"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Download the Acme Traders App")
        self.assertContains(response, 'id="steps"')

    def test_structured_data_is_valid_json(self):
        response = self.client.get(reverse("web:home"))
        html = response.content.decode()
        start = html.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
        data = json.loads(html[start:html.index("</script>", start)])
        types = [node["@type"] for node in data["@graph"]]
        self.assertEqual(types, ["Organization", "WebSite", "WebApplication", "ItemList"])


class AppFilesTests(TestCase):
    """The files a browser needs to install the site as an app."""

    def test_manifest(self):
        response = self.client.get(reverse("web:manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        data = json.loads(response.content)
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], reverse("dashboard:dashboard"))
        sizes = {icon["sizes"] for icon in data["icons"]}
        self.assertIn("192x192", sizes)
        self.assertIn("512x512", sizes)
        self.assertIn("maskable", {icon["purpose"] for icon in data["icons"]})

    def test_service_worker_served_from_root(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/javascript")
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertContains(response, 'const OFFLINE_URL = "/offline/"')

    def test_offline_page_is_public(self):
        self.assertEqual(self.client.get(reverse("web:offline")).status_code, 200)

    def test_signed_in_pages_offer_install_and_stay_out_of_search(self):
        user = User.objects.create_user("dealer1", password="pass12345")
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, "data-pwa-install")
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')

    def test_login_page_offers_install(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, "Install the app on this device")


class SearchEngineFilesTests(TestCase):

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Sitemap: https://order.initiatorsolutions.com/sitemap.xml")

    def test_sitemap_xml(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'<?xml version="1.0"'))
        self.assertContains(response, "<loc>https://order.initiatorsolutions.com/</loc>")
        self.assertContains(response, "<loc>https://order.initiatorsolutions.com/app/</loc>")

    def test_favicon_redirects_to_static(self):
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 301)
        self.assertTrue(response["Location"].endswith("assets/pwa/favicon.ico"))


class ServicesTests(TestCase):

    def test_short_name_fits_under_an_icon(self):
        company = Contact(name="Generous Technology Pvt Ltd", address="x")
        self.assertEqual(services.short_name(company), "Generous")
        self.assertEqual(services.short_name(None), "Order Mgmt")

    def test_json_ld_cannot_close_the_script_tag(self):
        self.assertNotIn("</script>", services.to_json_ld({"name": "</script><b>"}))
