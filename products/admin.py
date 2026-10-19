from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html, format_html_join

from .models import Brand, Product, Unit


class LookupAdmin(admin.ModelAdmin):
    """Shared setup for the one-field lookup tables."""

    list_display = ("name", "product_count", "created_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("name",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        # one COUNT for the whole page instead of one per row
        return super().get_queryset(request).annotate(_n=Count("products"))

    @admin.display(description="Products", ordering="_n")
    def product_count(self, obj):
        return obj._n


@admin.register(Brand)
class BrandAdmin(LookupAdmin):
    pass


@admin.register(Unit)
class UnitAdmin(LookupAdmin):
    pass


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("thumb", "name", "partno", "brand", "unit", "hsn",
                    "slab", "price", "net_price", "gross_price", "stock", "status")
    list_display_links = ("thumb", "name")
    list_filter = ("brand", "price_tax_type", "unit", "gst")
    search_fields = ("name", "partno", "hsn", "brand__name")
    list_select_related = ("brand", "unit")
    list_per_page = 25
    autocomplete_fields = ("brand", "unit")
    save_on_top = True
    readonly_fields = ("preview", "money", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("name", "partno", "brand", "desc")}),
        ("Tax & pricing", {"fields": ("unit", "hsn", "gst", "price", "price_tax_type", "money")}),
        ("Stock", {"fields": ("stock",)}),
        ("Images", {
            "fields": ("preview", "image_front", "image_back", "image_left", "image_right"),
            "description": "Leave any side blank to fall back to the placeholder image.",
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Status", ordering="stock")
    def status(self, obj):
        colour = {"out": "#dc3545", "low": "#fd7e14", "instock": "#198754"}[obj.stock_status]
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px;white-space:nowrap">{}</span>',
            colour, obj.stock_label,
        )

    @admin.display(description="GST", ordering="gst")
    def slab(self, obj):
        colour = "#6c757d" if obj.gst == 0 else "#0d6efd"
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:11px">{}</span>',
            colour, obj.get_gst_display(),
        )

    @admin.display(description="Net")
    def net_price(self, obj):
        return obj.price_excluding_gst

    @admin.display(description="Gross")
    def gross_price(self, obj):
        return obj.price_including_gst

    @admin.display(description="Works out as")
    def money(self, obj):
        if obj.pk is None:
            return "Save to see the net/gross breakdown."
        return format_html(
            '<table class="om-money">'
            "<tr><td>Net (before GST)</td><td><b>{}</b></td></tr>"
            "<tr><td>GST at {}</td><td><b>{}</b></td></tr>"
            "<tr><td>Gross (with GST)</td><td><b>{}</b></td></tr>"
            "</table>",
            obj.price_excluding_gst,
            obj.get_gst_display(),
            obj.price_including_gst - obj.price_excluding_gst,
            obj.price_including_gst,
        )

    @admin.display(description="")
    def thumb(self, obj):
        return format_html('<img class="om-thumb" src="{}" alt="">', obj.front_url)

    @admin.display(description="All sides")
    def preview(self, obj):
        if obj.pk is None:
            return "Save the product once to see its images here."
        # a wrapping flex row — the CSS sizes the tiles, so they reflow on a phone
        return format_html(
            '<div class="om-gallery">{}</div>',
            format_html_join(
                "",
                '<figure><img src="{}" alt="{}" loading="lazy"><figcaption>{}</figcaption></figure>',
                ((url, label, label) for label, url in obj.gallery),
            ),
        )
