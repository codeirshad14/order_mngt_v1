from decimal import ROUND_HALF_UP, Decimal

from django.db import models
from django.utils import timezone

from delaer.models import DealerProfile, SalesExecutive
from products.models import Product


class Order(models.Model):
    """A dealer's order. While it is a draft it doubles as their cart."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        HOLD = "hold", "On hold"
        FINAL = "final", "Final"

    dealer = models.ForeignKey(DealerProfile, on_delete=models.PROTECT, related_name="orders")

    # Who brought the order in. Empty means the dealer placed it themselves,
    # which is a real and common case — so this is nullable rather than
    # defaulted, and reports read an empty one as "direct".
    sales_executive = models.ForeignKey(
        SalesExecutive,
        on_delete=models.PROTECT,
        related_name="orders",
        null=True, blank=True,
        help_text="Leave empty when the dealer placed the order themselves.",
    )

    order_no = models.CharField(max_length=20, unique=True, blank=True)
    status = models.CharField(max_length=5, choices=Status.choices, default=Status.DRAFT)

    ordered_on = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Newest first, by primary key.
        #
        # It was "-created_at", which reads the same but is not dependable: two
        # orders saved in the same moment tie, and a tie leaves the database free
        # to return them in any order it likes. With a hundred rows to a page
        # that means a row can appear on two pages, or on none. The primary key
        # is unique and always increases, so it is the only ordering that both
        # puts the latest order on top and stays put between requests.
        #
        # Every plain listing of orders inherits this — the order table and the
        # Order Book both — and because Python's own sort is stable, the reports
        # that rank by value or age now break their ties newest-first too.
        ordering = ["-pk"]

    def __str__(self):
        return self.order_no or f"(unsaved order for {self.dealer})"

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = self._next_order_no()
        super().save(*args, **kwargs)

    @staticmethod
    def _next_order_no():
        """ORD-2026-0001, restarting each year."""
        prefix = f"ORD-{timezone.localdate().year}-"
        last = Order.objects.filter(order_no__startswith=prefix).order_by("-order_no").first()
        seq = int(last.order_no.rsplit("-", 1)[1]) + 1 if last else 1
        return f"{prefix}{seq:04d}"

    # ---- who put the order in ----
    @property
    def raised_by(self):
        """The salesman's name, or that the dealer ordered for themselves.

        For display only — nothing is decided on this. One place works it out
        so the order page, every report and the exports all word it the same.
        """
        return self.sales_executive.name if self.sales_executive_id else "Dealer"

    @property
    def raised_by_code(self):
        """The executive's code, or a dash for a dealer's own order."""
        return self.sales_executive.code if self.sales_executive_id else "—"

    @property
    def is_direct(self):
        """True when the dealer placed it themselves, with no salesman."""
        return self.sales_executive_id is None

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT

    @property
    def is_hold(self):
        return self.status == self.Status.HOLD

    @property
    def can_resume(self):
        """A held order can only be picked up again on the day it was made."""
        return self.is_hold and self.ordered_on == timezone.localdate()

    # ---- totals: always summed from the items, never stored ----
    @property
    def total_net(self):
        return sum((i.line_net for i in self.items.all()), Decimal("0.00"))

    @property
    def total_gst(self):
        return sum((i.line_gst for i in self.items.all()), Decimal("0.00"))

    @property
    def total_amount(self):
        return self.total_net + self.total_gst

    @property
    def total_qty(self):
        return sum(i.qty for i in self.items.all())

    @property
    def qty_by_unit(self):
        """Quantity totalled per unit — [("SET", 10), ("BOX", 5), …].

        One number across units says nothing: an order whose total_qty is 19
        can be ten SET, five BOX, three KG and one PCS, and nobody receiving
        it can act on "19". Codes are compared in upper case so a 'Set' row
        and a 'SET' row in the unit table do not split the total in two.
        """
        totals = {}
        for item in self.items.all():
            code = str(item.product.unit).strip().upper()
            totals[code] = totals.get(code, 0) + item.qty
        # biggest first, then alphabetical so the order never jitters
        return sorted(totals.items(), key=lambda pair: (-pair[1], pair[0]))

    @staticmethod
    def _halve(tax):
        """CGST and SGST are each half the tax. The odd paisa is kept in SGST
        so the two parts still add up to the whole — never lost to rounding."""
        cgst = (tax / 2).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return cgst, tax - cgst

    @property
    def gst_breakup(self):
        """Taxable value and tax per HSN and GST rate.

        One order routinely mixes slabs — 0%, 12% and 28% across three lines —
        so a single GST figure is not something an invoice can be checked
        against. Both the order page and the invoice show these rows.
        """
        groups = {}
        for item in self.items.all():
            key = (item.product.hsn, item.gst)
            row = groups.get(key)
            if row is None:
                row = groups[key] = {
                    "hsn": item.product.hsn,
                    "rate": item.gst,
                    # each half of an intra-state slab: 28% -> 14% + 14%
                    "half_rate": (item.gst / 2).quantize(Decimal("0.01")),
                    "qty": 0,
                    "taxable": Decimal("0.00"),
                    "tax": Decimal("0.00"),
                }
            row["qty"] += item.qty
            row["taxable"] += item.line_net
            row["tax"] += item.line_gst

        rows = sorted(groups.values(), key=lambda r: (r["rate"], r["hsn"]))
        for row in rows:
            row["cgst"], row["sgst"] = self._halve(row["tax"])
            row["igst"] = row["tax"]
        return rows

    # ---- stock check, before the order is placed ----
    @property
    def short_items(self):
        """Lines asking for more than there is in stock.

        Advisory only — it is what the order page shows so nobody is sent to
        a button that will fail. finalise() checks again inside a locked
        transaction, because stock can move between the two.
        """
        return [item for item in self.items.all() if item.is_short]

    @property
    def stock_ok(self):
        return not self.short_items

    @property
    def can_place(self):
        """Every condition the Place Order button depends on."""
        return self.is_draft and self.items.exists() and self.stock_ok


class OrderItem(models.Model):
    """One product line. Rate and GST are copied from the product when the
    line is added, so a later price change never rewrites an old order."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    qty = models.PositiveIntegerField(default=1)

    rate = models.DecimalField("Rate (net)", max_digits=12, decimal_places=2)
    gst = models.DecimalField("GST %", max_digits=5, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        # one line per product — adding the same product again bumps the qty
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="unique_product_per_order")
        ]

    def __str__(self):
        return f"{self.product} x{self.qty}"

    def save(self, *args, **kwargs):
        # price comes from the product master, never from user input
        if not self.rate:
            self.rate = self.product.price_excluding_gst
        if not self.gst:
            self.gst = self.product.gst
        super().save(*args, **kwargs)

    @property
    def line_net(self):
        return (self.rate * self.qty).quantize(Decimal("0.01"))

    @property
    def line_gst(self):
        return (self.line_net * self.gst / 100).quantize(Decimal("0.01"))

    @property
    def line_total(self):
        return self.line_net + self.line_gst

    # ---- stock, as it stands right now ----
    @property
    def in_stock(self):
        """What is on the shelf for this product at this moment.

        Read live rather than copied when the line was added: stock moves
        while a draft sits open, and the dealer needs the current figure.
        """
        return self.product.stock

    @property
    def shortfall(self):
        """How many more would be needed to place this line; 0 when it fits."""
        return max(0, self.qty - self.product.stock)

    @property
    def is_short(self):
        return self.shortfall > 0
