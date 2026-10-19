"""Attendance — a sales executive marking that they visited a dealer.

One model, one idea: a Visit. The executive picks the dealer, takes a photo
at the door, and the browser hands over the coordinates it was standing at.
Nothing here is edited afterwards — a visit is a record of a moment, so the
page only ever adds them.

Dealers have nothing to do with this app. Only a sales executive marks a
visit; management reads the report.
"""

from django.db import models
from django.utils import timezone

from delaer.models import DealerProfile, SalesExecutive


class Visit(models.Model):
    """One executive, at one dealer, at one moment."""

    sales_executive = models.ForeignKey(
        SalesExecutive, on_delete=models.PROTECT, related_name="visits",
    )
    dealer = models.ForeignKey(
        DealerProfile, on_delete=models.PROTECT, related_name="visits",
    )

    # taken at the door, on the phone's camera
    photo = models.ImageField("Visit photo", upload_to="visits/%Y/%m/")

    # Where the browser said the phone was. Nullable because permission can
    # be refused and the visit still happened — a record with no coordinates
    # is worth more than no record at all.
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
    )
    accuracy_m = models.PositiveIntegerField(
        "Accuracy (metres)", null=True, blank=True,
        help_text="How sure the phone was about the position it gave.",
    )

    place = models.CharField(
        "Approximate place", max_length=200, blank=True,
        help_text="Worked out from the coordinates when the visit was marked.",
    )

    note = models.CharField(max_length=200, blank=True)

    # the day the visit counts against — separate from created_at so a
    # report can group by date without worrying about time zones
    visited_on = models.DateField(default=timezone.localdate)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Visit"
        verbose_name_plural = "Visits"
        indexes = [
            # the report reads by executive and by date, in that order
            models.Index(fields=["sales_executive", "-visited_on"]),
            models.Index(fields=["dealer", "-visited_on"]),
        ]

    def __str__(self):
        return f"{self.sales_executive} visited {self.dealer} on {self.visited_on}"

    # ---- location ----
    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def where(self):
        """The place name if one was found, else the bare coordinates.

        The name is looked up once, in the browser, at the moment the visit
        is marked — never when a report is read. A report showing fifty
        visits would otherwise make fifty calls to a geocoder every time
        somebody opened it.
        """
        return self.place or self.coordinates or "—"

    @property
    def coordinates(self):
        """"26.912434, 75.787270" — what a person would paste into a map."""
        return f"{self.latitude}, {self.longitude}" if self.has_location else ""

    @property
    def map_url(self):
        """Opens the spot in Google Maps. A plain link needs no API key and
        works on a phone, which is where these get looked at."""
        if not self.has_location:
            return ""
        return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"

    @property
    def map_embed_url(self):
        """A small slippy map for the report, from OpenStreetMap.

        OSM rather than Google here because an embedded Google map needs a
        billing-enabled key, and this only has to show roughly where the
        photo was taken.
        """
        if not self.has_location:
            return ""
        lat, lng = float(self.latitude), float(self.longitude)
        span = 0.004                      # a few streets either way
        box = f"{lng - span},{lat - span},{lng + span},{lat + span}"
        return (
            "https://www.openstreetmap.org/export/embed.html"
            f"?bbox={box}&layer=mapnik&marker={lat},{lng}"
        )
