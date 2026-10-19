from django.db import models

from products.models import Product

# Create your models here.


class ProductGroup(models.Model):
    """Shared behaviour for the two named groups of products below.

    Abstract, so it creates no table of its own — Catelog and NewArrival each
    get their own table with these same fields.
    """

    name = models.CharField(max_length=120, unique=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def product_count(self):
        return self.products.count()

    @property
    def cover_url(self):
        """First product's front image, so the card has a picture."""
        first = self.products.first()
        return first.front_url if first else None


class Catelog(ProductGroup):
    """A named group of products, e.g. "Summer Range"."""

    products = models.ManyToManyField(Product, related_name="catelogs", blank=True)

    class Meta(ProductGroup.Meta):
        verbose_name = "Catelog"
        verbose_name_plural = "Catelogs"

    @property
    def new_arrival_count(self):
        """How many of this catelog's products are also in a new arrival list."""
        return self.products.filter(new_arrivals__isnull=False).distinct().count()


class NewArrival(ProductGroup):
    """A named list of products to show under New Arrivals. Kept separate from
    Catelog so a product can be new without belonging to any catelog."""

    products = models.ManyToManyField(Product, related_name="new_arrivals", blank=True)

    class Meta(ProductGroup.Meta):
        verbose_name = "New arrival"
        verbose_name_plural = "New arrivals"
