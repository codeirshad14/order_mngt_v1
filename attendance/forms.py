"""The one form this app has: marking a visit."""

from django import forms

from delaer.models import DealerProfile

from .models import Visit


class VisitForm(forms.ModelForm):
    """Dealer, photo, note. The coordinates ride along in hidden fields that
    the browser fills in — see initVisitCapture() in main.js."""

    class Meta:
        model = Visit
        fields = ["dealer", "photo", "note", "latitude", "longitude",
                  "accuracy_m", "place"]
        widgets = {
            "dealer": forms.Select(attrs={"class": "select"}),
            # capture="environment" asks a phone for the rear camera rather
            # than the gallery; a laptop quietly falls back to a file picker
            "photo": forms.ClearableFileInput(attrs={
                "class": "input",
                "accept": "image/*",
                "capture": "environment",
            }),
            "note": forms.TextInput(attrs={
                "class": "input",
                "placeholder": "Anything worth remembering about the visit",
            }),
            # filled in by the browser, never typed
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "accuracy_m": forms.HiddenInput(),
            "place": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["dealer"].queryset = DealerProfile.objects.all()
        self.fields["dealer"].empty_label = "Which dealer did you visit?"
        self.fields["photo"].label = "Photo at the dealer"
        self.fields["note"].required = False

    def clean_photo(self):
        """A visit without a photo is just a claim, so the photo is the one
        thing that cannot be skipped. Size is capped so a modern phone
        camera cannot fill the disk one visit at a time."""
        photo = self.cleaned_data.get("photo")
        if photo and photo.size > 8 * 1024 * 1024:
            raise forms.ValidationError("That photo is over 8 MB. Please retake it.")
        return photo
