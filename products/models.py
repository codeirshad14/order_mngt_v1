from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.templatetags.static import static

# shown wherever a product has no photo of its own
DEFAULT_IMAGE = "assets/imgs/product-placeholder.png"


class Brand(models.Model):
    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Unit(models.Model):
    name = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ProductQuerySet(models.QuerySet):
    """Search and stock filtering in one place.

    The products table, the shop cards and the topbar suggestions all call
    these, so a part number that finds a product in one of them finds it in
    the others too.
    """

    def search(self, term):
        """Products matching every word in `term`, in any of the fields a
        person would recognise a product by.

        Word by word rather than on the whole string: someone who remembers
        "star 340" gets "Star Refrigerator 340L", which a single icontains
        on the full phrase would miss.
        """
        products = self
        for word in (term or "").split():
            products = products.filter(
                Q(name__icontains=word)
                | Q(partno__icontains=word)
                | Q(brand__name__icontains=word)
                | Q(alias__icontains=word)
                | Q(category__icontains=word)
                | Q(barcode__icontains=word)
            )
        return products

    def in_stock_state(self, status):
        """Narrow to one of the stock_status values; anything else is 'all'."""
        if status == "out":
            return self.filter(stock=0)
        if status == "low":
            return self.filter(stock__gt=0, stock__lte=self.model.LOW_STOCK_AT)
        if status == "instock":
            return self.filter(stock__gt=self.model.LOW_STOCK_AT)
        return self


class Product(models.Model):
    """A sellable item. Four optional photos, one per side."""

    objects = ProductQuerySet.as_manager()

    class TaxType(models.TextChoices):
        INCLUSIVE = "inclusive", "Price includes GST"
        EXCLUSIVE = "exclusive", "Price excludes GST"

    # the GST slabs actually in use
    GST_CHOICES = [
        (Decimal("0.00"), "0%"),
        (Decimal("1.00"), "1%"),
        (Decimal("2.00"), "2%"),
        (Decimal("3.00"), "3%"),
        (Decimal("5.00"), "5%"),
        (Decimal("12.00"), "12%"),
        (Decimal("18.00"), "18%"),
        (Decimal("28.00"), "28%"),
        (Decimal("40.00"), "40%"),
    ]

    # ---- required ----
    name = models.CharField(max_length=200)
    partno = models.CharField("Part number", max_length=60, unique=True)
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="products")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="products")
    hsn = models.CharField("HSN code", max_length=8)
    gst = models.DecimalField(
        "GST %", max_digits=5, decimal_places=2, choices=GST_CHOICES, default=Decimal("18.00")
    )
    price = models.DecimalField(max_digits=12, decimal_places=2)
    price_tax_type = models.CharField(
        "Price is",
        max_length=9,
        choices=TaxType.choices,
        default=TaxType.EXCLUSIVE,
        help_text="Whether the price above already has GST in it.",
    )
    stock = models.PositiveIntegerField(default=0)

    # ---- from Tally / the mobile app ----
    # null rather than blank so many UI-created products can each have no
    # barcode without tripping the unique constraint
    barcode = models.CharField(max_length=64, unique=True, null=True, blank=True)
    alias = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=60, blank=True)
    retail_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tally_guid = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)

    # ---- optional ----
    desc = models.TextField("Description", blank=True)
    image_front = models.ImageField("Front image", upload_to="products/", blank=True)
    image_back = models.ImageField("Back image", upload_to="products/", blank=True)
    image_left = models.ImageField("Left image", upload_to="products/", blank=True)
    image_right = models.ImageField("Right image", upload_to="products/", blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.partno})"

    # ---- stock ----
    LOW_STOCK_AT = 5

    @property
    def stock_status(self):
        """Matches the data-status values the table filter buttons use."""
        if self.stock == 0:
            return "out"
        if self.stock <= self.LOW_STOCK_AT:
            return "low"
        return "instock"

    @property
    def stock_label(self):
        return {"out": "Out of stock", "low": "Low stock", "instock": "In stock"}[self.stock_status]

    @property
    def stock_badge(self):
        """Suffix for the badge--* class."""
        return {"out": "danger", "low": "warning", "instock": "success"}[self.stock_status]

    @property
    def initials(self):
        return "".join(w[0] for w in self.name.split()[:2]).upper()

    # ---- images ----
    @staticmethod
    def _url(field):
        """An ImageField is falsy when no file was uploaded."""
        return field.url if field else static(DEFAULT_IMAGE)

    @property
    def front_url(self):
        return self._url(self.image_front)

    @property
    def back_url(self):
        return self._url(self.image_back)

    @property
    def left_url(self):
        return self._url(self.image_left)

    @property
    def right_url(self):
        return self._url(self.image_right)

    @property
    def gallery(self):
        """(label, url) for each side — handy for looping in a template."""
        return [
            ("Front", self.front_url),
            ("Back", self.back_url),
            ("Left", self.left_url),
            ("Right", self.right_url),
        ]

    # ---- price ----
    @staticmethod
    def _dec(value):
        """Fields hold Decimal once loaded from the DB, but an unsaved instance
        keeps whatever was passed in — often plain ints."""
        return value if isinstance(value, Decimal) else Decimal(str(value))

    @property
    def price_excluding_gst(self):
        if self.price_tax_type == self.TaxType.EXCLUSIVE:
            return self._dec(self.price)
        rate = 1 + self._dec(self.gst) / 100
        return (self._dec(self.price) / rate).quantize(Decimal("0.01"))

    @property
    def price_including_gst(self):
        if self.price_tax_type == self.TaxType.INCLUSIVE:
            return self._dec(self.price)
        rate = 1 + self._dec(self.gst) / 100
        return (self._dec(self.price) * rate).quantize(Decimal("0.01"))
