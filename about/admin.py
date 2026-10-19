from django.contrib import admin
from django import forms

from .models import About

# Register your models here.


class AboutForm(forms.ModelForm):
    class Meta:
        model = About
        fields = "__all__"
        # the class is what admin-richtext.js looks for
        widgets = {"description": forms.Textarea(attrs={"class": "richtext", "rows": 20})}

    class Media:
        # TinyMCE from cdnjs — no API key needed there, and nothing extra to
        # install into the virtualenv
        js = (
            "https://cdnjs.cloudflare.com/ajax/libs/tinymce/6.8.3/tinymce.min.js",
            "assets/js/admin-richtext.js",
        )


@admin.register(About)
class AboutAdmin(admin.ModelAdmin):
    form = AboutForm
    list_display = ("title", "is_active", "updated_at")
    list_editable = ("is_active",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("title", "logo", "is_active")}),
        ("Description", {"fields": ("description",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
