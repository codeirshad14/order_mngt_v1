import secrets

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

# 22AAAAA0000A1Z5 — state code, PAN, entity no, 'Z', checksum
GSTIN_VALIDATOR = RegexValidator(
    r"^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z\d]Z[A-Z\d]$",
    "Enter a valid 15-character GSTIN, for example 27ABCDE1234F1Z5.",
)

MOBILE_VALIDATOR = RegexValidator(
    r"^[6-9]\d{9}$",
    "Enter a 10-digit mobile number starting with 6, 7, 8 or 9.",
)


class SalesExecutive(models.Model):
    """A salesman: one profile per login, same shape as a dealer's.

    Created in the Django admin only — there is no sign-up form and no view
    that writes one. Having the profile is what makes a login a salesman, so
    handing one out is a deliberate act by an administrator.

    A salesman places orders on behalf of a dealer: they choose the dealer,
    and the order records them as the one who brought it in. An order a
    dealer places for themselves has no salesman on it.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_profile",
    )

    name = models.CharField("Full name", max_length=200)
    code = models.CharField(
        max_length=20, unique=True, blank=True,
        help_text="Left blank, the next SE-0001 is allotted on save.",
    )

    mobile = models.CharField("Mobile", max_length=10, validators=[MOBILE_VALIDATOR])
    email = models.EmailField("Email", blank=True)
    territory = models.CharField(
        max_length=120, blank=True,
        help_text="Area or region this executive covers. For reporting only.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Untick to stop new orders being raised in this name, "
                  "without touching the orders already placed.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Sales executive"
        verbose_name_plural = "Sales executives"

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self._next_code()
        super().save(*args, **kwargs)

    @staticmethod
    def _next_code():
        """SE-0001, counting on from the highest already allotted."""
        last = SalesExecutive.objects.filter(code__startswith="SE-").order_by("-code").first()
        seq = int(last.code.rsplit("-", 1)[1]) + 1 if last else 1
        return f"SE-{seq:04d}"

    @property
    def initials(self):
        return "".join(word[0] for word in self.name.split()[:2]).upper()


class DealerProfile(models.Model):
    """The company details behind one login — one profile per user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dealer_profile",
    )

    name = models.CharField("Company name", max_length=200)
    address = models.TextField("Address")
    state = models.CharField(
        max_length=80, blank=True,
        help_text="Decides CGST+SGST (same state as us) or IGST (different).",
    )
    gstin = models.CharField("GSTIN", max_length=15, unique=True, validators=[GSTIN_VALIDATOR])
    mobile = models.CharField("Mobile", max_length=10, validators=[MOBILE_VALIDATOR])
    email = models.EmailField("Email")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Dealer profile"
        verbose_name_plural = "Dealer profiles"

    def __str__(self):
        return self.name

    @property
    def address_lines(self):
        """The textarea is free text — split it for display."""
        return [line for line in self.address.splitlines() if line.strip()]

    @property
    def state_code(self):
        """First two digits of the GSTIN identify the state."""
        return self.gstin[:2] if self.gstin else ""

    @property
    def initials(self):
        return "".join(w[0] for w in self.name.split()[:2]).upper()


class ApiKey(models.Model):
    """A key the mobile app or Tally sends in the X-API-Key header.

    Create one per integration in the admin; the key is generated on save.
    """

    label = models.CharField(max_length=100, help_text="e.g. Mobile app, Tally sync")
    key = models.CharField(max_length=64, unique=True, editable=False, db_index=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_keys",
        help_text="Requests with this key act as this user.",
    )
    dealer = models.ForeignKey(
        DealerProfile, on_delete=models.CASCADE, related_name="api_keys",
        null=True, blank=True,
        help_text="Optional — the dealer this integration belongs to.",
    )

    is_active = models.BooleanField(default=True, help_text="Untick to revoke without deleting.")
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "API key"
        verbose_name_plural = "API keys"

    def __str__(self):
        return f"{self.label} ({self.masked})"

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(24)     # 48 characters
        super().save(*args, **kwargs)

    @property
    def masked(self):
        """Safe to show in a list — never the whole key."""
        return f"{self.key[:6]}…{self.key[-4:]}" if self.key else ""

    def touch(self):
        """Record that the key was just used, without a full save()."""
        ApiKey.objects.filter(pk=self.pk).update(last_used_at=timezone.now())
