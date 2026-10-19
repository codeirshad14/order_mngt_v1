from django.core.validators import RegexValidator
from django.db import models

# Create your models here.

IFSC_VALIDATOR = RegexValidator(
    r"^[A-Z]{4}0[A-Z0-9]{6}$",
    "IFSC must be 11 characters, e.g. HDFC0001234.",
)

ACCOUNT_VALIDATOR = RegexValidator(
    r"^\d{9,18}$",
    "Account number must be 9 to 18 digits.",
)

UPI_VALIDATOR = RegexValidator(
    r"^[\w.\-]{2,60}@[a-zA-Z]{2,20}$",
    "UPI ID looks like name@bank, e.g. sharma@okhdfcbank.",
)


class BankDetail(models.Model):
    """One bank account people can pay into."""

    class AccountType(models.TextChoices):
        CURRENT = "current", "Current"
        SAVINGS = "savings", "Savings"
        CC = "cc", "Cash Credit"
        OD = "od", "Overdraft"

    label = models.CharField(
        max_length=120, default="Primary Account",
        help_text="How this account is referred to internally.",
    )
    is_primary = models.BooleanField(
        "Primary account", default=False,
        help_text="Shown first on the bank details page.",
    )

    # ---- the account ----
    account_name = models.CharField("Account holder", max_length=150)
    account_number = models.CharField(max_length=18, unique=True, validators=[ACCOUNT_VALIDATOR])
    account_type = models.CharField(max_length=7, choices=AccountType.choices, default=AccountType.CURRENT)

    # ---- the bank ----
    bank_name = models.CharField(max_length=120)
    branch = models.CharField(max_length=120, blank=True)
    ifsc = models.CharField("IFSC", max_length=11, validators=[IFSC_VALIDATOR])
    micr = models.CharField("MICR", max_length=9, blank=True)
    swift = models.CharField("SWIFT / BIC", max_length=11, blank=True,
                             help_text="Only needed for payments from abroad.")

    # ---- UPI ----
    upi_id = models.CharField("UPI ID", max_length=80, blank=True, validators=[UPI_VALIDATOR])
    upi_qr = models.ImageField("UPI QR code", upload_to="bank/upi/", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_primary", "bank_name"]
        verbose_name = "Bank detail"
        verbose_name_plural = "Bank details"

    def __str__(self):
        return f"{self.bank_name} — {self.masked_account}"

    @property
    def masked_account(self):
        """Last four digits only, for anywhere the full number isn't wanted."""
        return f"XXXX{self.account_number[-4:]}" if self.account_number else ""

    @property
    def has_upi(self):
        return bool(self.upi_id or self.upi_qr)
