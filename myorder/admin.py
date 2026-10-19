from django.contrib import admin

from .models import Order, OrderItem

# Register your models here.


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ("product",)
    # rate and gst are snapshots taken from the product, so they are shown but
    # not editable. The timestamps are left out — in a tabular inline they add
    # two wide columns and push the row off the page.
    fields = ("product", "qty", "rate", "gst", "line_total")
    readonly_fields = ("rate", "gst", "line_total")

    @admin.display(description="Line total")
    def line_total(self, obj):
        return obj.line_total if obj.pk else "—"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "dealer", "ordered_on", "status", "total_qty", "total_amount")
    list_filter = ("status", "ordered_on")
    search_fields = ("order_no", "dealer__name")
    list_select_related = ("dealer",)
    readonly_fields = ("order_no", "created_at", "updated_at")
    inlines = [OrderItemInline]

    fieldsets = (
        (None, {"fields": ("order_no", "dealer", "status", "ordered_on")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )
