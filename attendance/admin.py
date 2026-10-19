from django.contrib import admin
from django.utils.html import format_html

from .models import Visit


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    """Visits are marked in the field, not here — this is for looking back."""

    list_display = ("visited_on", "sales_executive", "dealer", "place", "where", "thumb")
    list_filter = ("visited_on", "sales_executive", "dealer")
    list_select_related = ("sales_executive", "dealer")
    date_hierarchy = "visited_on"
    search_fields = (
        "sales_executive__name", "sales_executive__code",
        "dealer__name", "note", "place",
    )
    autocomplete_fields = ("sales_executive", "dealer")
    readonly_fields = ("preview", "where", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("sales_executive", "dealer", "visited_on", "note")}),
        ("Photo", {"fields": ("photo", "preview")}),
        ("Location", {
            "fields": ("latitude", "longitude", "accuracy_m", "place", "where"),
            "description": "Captured by the browser when the visit was marked.",
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Location")
    def where(self, obj):
        if not obj.has_location:
            return "—"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{} (±{} m)</a>',
            obj.map_url, obj.coordinates, obj.accuracy_m or "?",
        )

    @admin.display(description="Photo")
    def thumb(self, obj):
        if not obj.photo:
            return "—"
        return format_html(
            '<img src="{}" style="height:38px;border-radius:4px" alt="">', obj.photo.url
        )

    @admin.display(description="Photo")
    def preview(self, obj):
        if not obj.photo:
            return "—"
        return format_html(
            '<img src="{}" style="max-width:320px;border-radius:8px" alt="">', obj.photo.url
        )
