"""Catelog and New Arrival serializers.

Each one carries two fields and nothing else:

    name        the group's own name, which is also how it is matched
    products    the products in it, as a list of product names

Products go in and out as **names**, the same way brand and unit do on the
product API, so a caller never has to know our ids. A name that is not in the
catalogue is reported rather than quietly dropped — a typo that silently
emptied a catelog would be worse than a failed row.

The two models are identical apart from the table they live in, so the work is
done once in GroupSerializer and each one just points at its own model.
"""

from rest_framework import serializers

from products.models import Product

from .models import Catelog, NewArrival


class GroupSerializer(serializers.ModelSerializer):
    """Shared by both. Meta.model is filled in by the two below."""

    # A list of product names coming in. write_only because the field on the
    # model is a many-to-many manager, not a list: left readable, DRF would try
    # to iterate the manager itself and fall over. The names are put back into
    # the response by to_representation below.
    products = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True,
    )

    class Meta:
        fields = ["name", "products"]

    def to_representation(self, group):
        """Send the products back as names, the way they came in."""
        data = super().to_representation(group)
        data["products"] = [p.name for p in group.products.all()]
        return data

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("A name is required.")
        return value

    def validate_products(self, names):
        """Turn the list of product names into product rows.

        Done here, during validation, rather than in create()/update() — an
        error raised in those runs after is_valid() has already passed, so DRF
        turns it into a 400 for the whole request. A sync posting fifty
        catelogs would lose all fifty because of one typo. Raised here it lands
        in serializer.errors instead, and api.py reports that one row and
        carries on with the rest.

        Case is ignored, so "app 1" finds "APP 1", and every unknown name is
        reported together rather than one per attempt.
        """
        found, missing = [], []

        for name in names:
            name = (name or "").strip()
            if not name:
                continue
            product = Product.objects.filter(name__iexact=name).order_by("pk").first()
            if product is None:
                missing.append(name)
            else:
                found.append(product)

        if missing:
            raise serializers.ValidationError(
                [f"No product named {n!r}." for n in missing]
            )
        return found

    def create(self, validated_data):
        # already Product rows by now, courtesy of validate_products
        products = validated_data.pop("products", [])
        group = super().create(validated_data)
        # set() needs the row to exist first, so this follows the create
        group.products.set(products)
        return group

    def update(self, instance, validated_data):
        products = validated_data.pop("products", None)
        group = super().update(instance, validated_data)

        # products left out of a PATCH are left alone; an empty list is taken
        # at its word and clears the group
        if products is not None:
            group.products.set(products)
        return group


class CatelogSerializer(GroupSerializer):
    class Meta(GroupSerializer.Meta):
        model = Catelog


class NewArrivalSerializer(GroupSerializer):
    class Meta(GroupSerializer.Meta):
        model = NewArrival
