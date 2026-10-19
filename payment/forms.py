from django import forms

from myorder.models import Order

from .models import Payment


class PaymentForm(forms.ModelForm):
    """Record money received. Pick an order to settle it, or leave the order
    empty to record an advance."""

    class Meta:
        model = Payment
        fields = ["dealer", "order", "amount", "paid_on", "mode", "reference", "note"]
        widgets = {
            "dealer": forms.Select(attrs={"class": "select"}),
            "order": forms.Select(attrs={"class": "select"}),
            "amount": forms.NumberInput(attrs={"class": "input", "step": "0.01", "min": "0.01"}),
            "paid_on": forms.DateInput(attrs={"class": "input", "type": "date"}),
            "mode": forms.Select(attrs={"class": "select"}),
            "reference": forms.TextInput(attrs={"class": "input", "placeholder": "UTR / cheque no"}),
            "note": forms.Textarea(attrs={"class": "textarea", "rows": 2}),
        }

    def __init__(self, *args, dealer=None, **kwargs):
        """`dealer` is the signed-in dealer. When given, the payment is locked
        to them and the order list is limited to their placed orders."""
        super().__init__(*args, **kwargs)

        self.fields["order"].empty_label = "Advance payment (no order)"
        self.fields["order"].queryset = Order.objects.filter(
            status=Order.Status.FINAL
        ).select_related("dealer")

        if dealer is not None:
            self.fields["dealer"].queryset = self.fields["dealer"].queryset.filter(pk=dealer.pk)
            self.fields["dealer"].initial = dealer
            self.fields["dealer"].widget = forms.HiddenInput()
            self.fields["order"].queryset = self.fields["order"].queryset.filter(dealer=dealer)

        # show the order number and what it was worth
        self.fields["order"].label_from_instance = (
            lambda o: f"{o.order_no} · {o.ordered_on:%d %b %Y} · {o.total_amount}"
        )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Amount must be more than zero.")
        return amount

    def clean(self):
        cleaned = super().clean()
        order, dealer = cleaned.get("order"), cleaned.get("dealer")

        # a payment must never land on another dealer's order
        if order and dealer and order.dealer_id != dealer.pk:
            self.add_error("order", f"That order belongs to {order.dealer.name}.")
        return cleaned
