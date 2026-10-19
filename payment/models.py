from decimal import Decimal

from django.db import models
from django.utils import timezone

from delaer.models import DealerProfile
from myorder.models import Order

# Create your models here.


class Payment(models.Model):
    """Money received from a dealer.

    Link it to an order to settle that order, or leave the order empty to
    record an advance — money taken before there is an order to put it against.
    """

    class Mode(models.TextChoices):
        CASH = "cash", "Cash"
        UPI = "upi", "UPI"
        NEFT = "neft", "NEFT / RTGS"
        CHEQUE = "cheque", "Cheque"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    receipt_no = models.CharField(max_length=20, unique=True, blank=True)
    dealer = models.ForeignKey(DealerProfile, on_delete=models.PROTECT, related_name="payments")

    # empty means it is an advance, not tied to any one order
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments",
        help_text="Leave empty for an advance payment.",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateField(default=timezone.localdate)
    mode = models.CharField(max_length=6, choices=Mode.choices, default=Mode.UPI)
    reference = models.CharField(
        max_length=60, blank=True,
        help_text="UTR, cheque number or transaction id.",
    )
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-paid_on", "-created_at"]

    def __str__(self):
        return f"{self.receipt_no} — {self.amount}"

    def save(self, *args, **kwargs):
        if not self.receipt_no:
            self.receipt_no = self._next_receipt_no()
        super().save(*args, **kwargs)

    @staticmethod
    def _next_receipt_no():
        """PMT-2026-0001, restarting each year."""
        prefix = f"PMT-{timezone.localdate().year}-"
        last = (
            Payment.objects.filter(receipt_no__startswith=prefix)
            .order_by("-receipt_no")
            .first()
        )
        seq = int(last.receipt_no.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:04d}"

    @property
    def is_advance(self):
        return self.order_id is None

    @property
    def against(self):
        """What this receipt was for, for display."""
        return self.order.order_no if self.order_id else "Advance"


def order_paid(order):
    """How much has been received against one order."""
    total = order.payments.aggregate(t=models.Sum("amount"))["t"]
    return total or Decimal("0.00")


def order_balance(order):
    """What is still owed on one order. Never negative — anything paid over
    the order's value is treated as advance and shows in the dealer ledger."""
    due = order.total_amount - order_paid(order)
    return due if due > 0 else Decimal("0.00")
