from django import forms

from .models import BankDetail


class BankDetailForm(forms.ModelForm):
    class Meta:
        model = BankDetail
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tidy the raw input before validation. A clean_<field>() method runs
        # after the field's validators, by which point a lowercase IFSC has
        # already failed its regex.
        if not self.data:
            return

        data = self.data.copy()

        for field in ("ifsc", "swift"):
            if data.get(field):
                data[field] = data[field].strip().upper()

        if data.get("upi_id"):
            data["upi_id"] = data["upi_id"].strip().lower()

        # people type account numbers with spaces or dashes
        if data.get("account_number"):
            number = data["account_number"]
            for junk in (" ", "-"):
                number = number.replace(junk, "")
            data["account_number"] = number.strip()

        self.data = data
