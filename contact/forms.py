import re

from django import forms

from .models import Contact

# pulls the src="..." out of a pasted <iframe ...> snippet
IFRAME_SRC = re.compile(r'src\s*=\s*["\']([^"\']+)["\']', re.I)


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # People copy the whole embed snippet out of Google Maps. Take the src
        # from it here, before validation — map_embed_url is a URLField, so a
        # clean_<field>() method would run too late and the tag would already
        # have been rejected as an invalid URL.
        self._iframe_without_src = False

        if self.data and self.data.get("map_embed_url", "").strip().lower().startswith("<iframe"):
            data = self.data.copy()
            found = IFRAME_SRC.search(data["map_embed_url"])
            data["map_embed_url"] = found.group(1) if found else ""
            self._iframe_without_src = found is None
            self.data = data

    def clean_map_embed_url(self):
        # the field is optional, so a blanked-out paste would otherwise save
        # quietly and look like the map had been stored
        if self._iframe_without_src:
            raise forms.ValidationError("That iframe tag has no src= to take the map link from.")
        return self.cleaned_data["map_embed_url"]
