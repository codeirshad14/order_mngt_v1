from django.contrib import admin

from .forms import ContactForm
from .models import Contact

# Register your models here.


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    form = ContactForm
    list_display = ("name", "city", "phone", "email", "is_primary", "updated_at")
    list_filter = ("is_primary", "city")
    list_editable = ("is_primary",)
    search_fields = ("name", "city", "email", "phone", "mobile")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("name", "logo", "gstin", "is_primary")}),
        ("Invoice", {
            "fields": ("terms",),
            "description": "Terms &amp; conditions printed at the foot of every "
                           "order invoice — one condition per line.",
        }),
        ("Address", {"fields": ("address", "city", "state", "pincode")}),
        ("Reach us", {"fields": ("phone", "mobile", "whatsapp", "email", "website", "working_hours")}),
        ("Map", {
            "fields": ("map_embed_url",),
            "description": "Paste the Google Maps embed link, or the whole "
                           "&lt;iframe&gt; tag — the src is taken out of it.",
        }),
        ("Social", {"fields": ("facebook", "instagram", "linkedin", "youtube"), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
