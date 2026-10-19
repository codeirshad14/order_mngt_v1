"""Product API serializer.

Carries these 17 fields and nothing else:

    name, partno, brand, unit, hsn, gst, price, price_tax_type, stock,
    barcode, alias, category, retail_price, wholesale_price, tally_guid,
    is_active, desc

Anything else in the request is ignored — images are not here at all, so no
API call can change a product's photos.
"""

from rest_framework import serializers

from .models import Brand, Product, Unit


class ProductSerializer(serializers.ModelSerializer):
    """One product, in and out."""

    # brand and unit go in and out as names, so the caller never needs our ids
    brand = serializers.CharField(required=False, allow_blank=True)
    unit = serializers.CharField(required=False, allow_blank=True)

    # the model needs these, but a sync may not send them. create() fills them
    # in, which only works if validation lets them through first.
    partno = serializers.CharField(required=False, allow_blank=True, max_length=60)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)

    # plain, so "5" is accepted; the model's GST_CHOICES are for the admin
    # dropdown and would only match the exact string "5.00"
    gst = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)

    class Meta:
        model = Product
        fields = [
            "name",
            "partno",
            "brand",
            "unit",
            "hsn",
            "gst",
            "price",
            "price_tax_type",
            "stock",
            "barcode",
            "alias",
            "category",
            "retail_price",
            "wholesale_price",
            "tally_guid",
            "is_active",
            "desc",
        ]

    def to_representation(self, product):
        """Send brand and unit back as names, the same way they came in."""
        data = super().to_representation(product)
        data["brand"] = product.brand.name if product.brand_id else ""
        data["unit"] = product.unit.name if product.unit_id else ""
        return data

    def validate_gst(self, value):
        if value < 0 or value > 100:
            raise serializers.ValidationError("GST must be between 0 and 100.")
        return value

    def validate_barcode(self, value):
        # "" would clash with every other blank on a unique column
        return value or None

    def _names_to_rows(self, data):
        """Swap the brand and unit names for the rows the model wants,
        creating either if it is new."""
        brand = (data.pop("brand", "") or "").strip()
        unit = (data.pop("unit", "") or "").strip()

        if brand:
            data["brand"] = Brand.objects.get_or_create(name=brand)[0]
        if unit:
            data["unit"] = Unit.objects.get_or_create(name=unit)[0]
        return data

    def _make_partno(self, name):
        """partno is required and unique. Build one from the name, adding -2,
        -3 and so on until it is free."""
        partno = (name or "API").strip()[:55] or "API"
        number = 1
        while Product.objects.filter(partno=partno).exists():
            number += 1
            partno = f"{(name or 'API').strip()[:52]}-{number}"
        return partno

    def create(self, validated_data):
        data = self._names_to_rows(validated_data)

        # sensible stand-ins for what the model insists on but a sync may omit
        data.setdefault("brand", Brand.objects.get_or_create(name="Unbranded")[0])
        data.setdefault("unit", Unit.objects.get_or_create(name="PCS")[0])
        if not data.get("partno"):
            data["partno"] = self._make_partno(data.get("name"))
        # a payload with retail_price but no price is common; use it
        data.setdefault("price", data.get("retail_price") or 0)

        return super().create(data)

    def update(self, instance, validated_data):
        return super().update(instance, self._names_to_rows(validated_data))
