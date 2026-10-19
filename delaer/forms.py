from django import forms

from .models import DealerProfile


class DealerProfileForm(forms.ModelForm):
    class Meta:
        model = DealerProfile
        fields = ["name", "address", "state", "gstin", "mobile", "email"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "input", "placeholder": "Sharma Traders Pvt Ltd",
            }),
            "address": forms.Textarea(attrs={
                "class": "textarea", "rows": 3,
                "placeholder": "Shop 14, MG Road\nAndheri East\nMumbai 400069",
            }),
            "state": forms.TextInput(attrs={"class": "input", "placeholder": "Maharashtra"}),
            "gstin": forms.TextInput(attrs={
                "class": "input", "placeholder": "27ABCDE1234F1Z5",
                "maxlength": 15, "style": "text-transform:uppercase",
            }),
            "mobile": forms.TextInput(attrs={
                "class": "input", "placeholder": "9876543210",
                "inputmode": "numeric", "maxlength": 10,
            }),
            "email": forms.EmailInput(attrs={
                "class": "input", "placeholder": "accounts@example.com",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tidy the raw input *before* validation. A clean_<field>() method runs
        # after the field's own validators, which is too late — a lowercase
        # GSTIN would already have failed the regex, and "+91 98765-43210"
        # would already have failed max_length.
        if self.data:
            data = self.data.copy()

            if data.get("gstin"):
                data["gstin"] = data["gstin"].strip().upper()

            if data.get("mobile"):
                mobile = data["mobile"]
                for junk in (" ", "-", "(", ")", "+91"):
                    mobile = mobile.replace(junk, "")
                data["mobile"] = mobile.strip()

            self.data = data
