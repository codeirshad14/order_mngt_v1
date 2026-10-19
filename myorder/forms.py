from django import forms

from products.models import Product

from .models import OrderItem


class OrderItemForm(forms.ModelForm):
    """Pick a product and a quantity. Rate and GST are not editable — the
    model copies them from the product master on save."""

    class Meta:
        model = OrderItem
        fields = ["product", "qty"]
        widgets = {
            "product": forms.Select(attrs={"class": "select"}),
            "qty": forms.NumberInput(attrs={"class": "input", "min": "1", "step": "1", "value": "1"}),
        }

    def __init__(self, *args, order=None, **kwargs):
        # the order being added to, so clean() can weigh the quantity against
        # what is already on it rather than against this box alone
        self.order = order
        super().__init__(*args, **kwargs)
        # only things actually in stock can be ordered
        self.fields["product"].queryset = Product.objects.select_related("brand").filter(stock__gt=0)
        self.fields["product"].empty_label = "Choose a product…"
        # brand and stock in the label so the search box above can match on
        # them too — it filters the option text
        self.fields["product"].label_from_instance = (
            lambda p: f"{p.name} · {p.partno} · {p.brand} · {p.stock} in stock"
        )

    def clean_qty(self):
        qty = self.cleaned_data["qty"]
        if qty < 1:
            raise forms.ValidationError("Quantity must be at least 1.")
        return qty

    def clean(self):
        cleaned = super().clean()
        product, qty = cleaned.get("product"), cleaned.get("qty")
        if not (product and qty):
            return cleaned

        # adding the same product again bumps the existing line, so the figure
        # that has to fit in stock is the two together
        already = 0
        if self.order is not None:
            line = self.order.items.filter(product=product).first()
            already = line.qty if line else 0

        if already + qty > product.stock:
            if already:
                self.add_error(
                    "qty",
                    f"Only {product.stock} in stock, and {already} "
                    f"already on this order.",
                )
            else:
                self.add_error("qty", f"Only {product.stock} in stock.")
        return cleaned
