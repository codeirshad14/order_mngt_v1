from django.db import models

# Create your models here.


class Contact(models.Model):
    """One office / branch worth of contact details."""

    # ---- who ----
    name = models.CharField("Office name", max_length=150)
    logo = models.ImageField(
        upload_to="company/", blank=True,
        help_text="Shown on the invoice letterhead.",
    )
    is_primary = models.BooleanField(
        "Head office", default=False,
        help_text="Shown first on the contact page, and used on invoices.",
    )
    gstin = models.CharField("GSTIN", max_length=15, blank=True)

    # ---- where ----
    address = models.TextField("Address")
    city = models.CharField(max_length=80, blank=True)
    state = models.CharField(max_length=80, blank=True)
    pincode = models.CharField(max_length=10, blank=True)

    # ---- how to reach ----
    phone = models.CharField(max_length=20, blank=True)
    mobile = models.CharField(max_length=20, blank=True)
    whatsapp = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    working_hours = models.CharField(
        max_length=120, blank=True,
        help_text="e.g. Mon–Sat, 10:00 am – 7:00 pm",
    )

    # ---- map ----
    # Only the embed URL is stored, never raw <iframe> HTML — saving markup
    # from a form and printing it back would be an injection hole. The form
    # pulls the src out if the whole embed snippet is pasted in.
    map_embed_url = models.URLField(
        "Map embed URL", max_length=600, blank=True,
        help_text="Google Maps → Share → Embed a map → copy the src (or paste "
                  "the whole iframe tag and the src is taken from it).",
    )

    # ---- invoice ----
    terms = models.TextField(
        "Terms & conditions", blank=True,
        help_text="Printed at the foot of the order invoice. One per line.",
    )

    # ---- social ----
    facebook = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    youtube = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "name"]
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"

    def __str__(self):
        return self.name

    @property
    def address_lines(self):
        """The textarea is free text — split it for display."""
        return [line for line in self.address.splitlines() if line.strip()]

    @property
    def city_line(self):
        """"Mumbai, Maharashtra 400069" from whichever parts are filled in."""
        town = ", ".join(p for p in (self.city, self.state) if p)
        return f"{town} {self.pincode}".strip()

    @property
    def terms_lines(self):
        """The textarea is free text — split it into numbered points."""
        return [line.strip() for line in self.terms.splitlines() if line.strip()]

    @property
    def socials(self):
        """(label, icon, url) for each social link that has been filled in."""
        links = [
            ("Facebook", "logo-facebook", self.facebook),
            ("Instagram", "logo-instagram", self.instagram),
            ("LinkedIn", "logo-linkedin", self.linkedin),
            ("YouTube", "logo-youtube", self.youtube),
        ]
        return [(label, icon, url) for label, icon, url in links if url]
