from django.contrib import admin

from .models import Catelog, NewArrival

# Register your models here.


class ProductGroupAdmin(admin.ModelAdmin):
    """Shared admin for Catelog and NewArrival — both are just a name plus a
    set of products, so the selection UI is defined once here."""

    list_display = ("name", "product_count", "updated_at")
    search_fields = ("name",)
    readonly_fields = ("created_at", "updated_at")

    # Two-pane picker with a search box above it: type to narrow the left
    # list, double-click or use the arrows to move products across, and the
    # right pane always shows exactly what is selected. Easier to work with
    # than a plain multi-select once there are a lot of products.
    filter_horizontal = ("products",)

    fieldsets = (
        (None, {"fields": ("name",)}),
        ("Products", {
            "fields": ("products",),
            "description": "Use the search box to narrow the list, then move "
                           "products to the right. A product can belong to "
                           "several catelogs and new arrival lists at once.",
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(Catelog)
class CatelogAdmin(ProductGroupAdmin):
    list_display = ("name", "product_count", "new_arrival_count", "updated_at")


@admin.register(NewArrival)
class NewArrivalAdmin(ProductGroupAdmin):
    pass
