from django import forms

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "partno",
            "brand",
            "desc",
            "unit",
            "hsn",
            "gst",
            "price",
            "price_tax_type",
            "stock",
            "image_front",
            "image_back",
            "image_left",
            "image_right",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input", "placeholder": "Star Refrigerator 340L"}),
            "partno": forms.TextInput(attrs={"class": "input", "placeholder": "SKU-1041"}),
            "brand": forms.Select(attrs={"class": "select"}),
            "desc": forms.Textarea(attrs={"class": "textarea", "rows": 4}),
            "unit": forms.Select(attrs={"class": "select"}),
            "hsn": forms.TextInput(attrs={"class": "input", "placeholder": "8418"}),
            "gst": forms.Select(attrs={"class": "select"}),
            "price": forms.NumberInput(attrs={"class": "input", "step": "0.01", "min": "0"}),
            "price_tax_type": forms.RadioSelect(),
            "stock": forms.NumberInput(attrs={"class": "input", "min": "0", "step": "1"}),
            "image_front": forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
            "image_back": forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
            "image_left": forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
            "image_right": forms.ClearableFileInput(attrs={"class": "input", "accept": "image/*"}),
        }

    def clean_partno(self):
        # part numbers are quoted in caps everywhere else in the system
        return self.cleaned_data["partno"].strip().upper()
