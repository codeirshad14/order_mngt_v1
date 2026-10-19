from django.contrib import admin
from django.utils.html import format_html

from .models import ApiKey, DealerProfile, SalesExecutive

# Register your models here.


@admin.register(SalesExecutive)
class SalesExecutiveAdmin(admin.ModelAdmin):
    """The only way a sales executive is created.

    There is deliberately no sign-up page and no view that writes one: giving
    a login this profile is what makes it a salesman, so it stays an
    administrator's decision.
    """

    list_display = ("code", "name", "user", "mobile", "territory", "is_active", "updated_at")
    list_filter = ("is_active", "territory")
    list_editable = ("is_active",)
    search_fields = ("code", "name", "mobile", "email", "territory", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = ("code", "created_at", "updated_at")

    fieldsets = (
        (None, {
            "fields": ("user", "name", "code", "is_active"),
            "description": "The login this profile belongs to becomes a sales "
                           "executive. They can then raise orders for any "
                           "dealer, and will see only the orders in their name.",
        }),
        ("Contact", {"fields": ("mobile", "email", "territory")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(DealerProfile)
class DealerProfileAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "gstin", "mobile", "email", "updated_at")
    list_select_related = ("user",)
    search_fields = ("name", "gstin", "mobile", "email", "user__username")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("user", "name")}),
        ("Contact", {"fields": ("address", "state", "mobile", "email")}),
        ("Tax", {"fields": ("gstin",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(ApiKey)
class ApiKeyAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "dealer", "masked", "is_active", "last_used_at")
    list_filter = ("is_active",)
    list_editable = ("is_active",)
    search_fields = ("label", "user__username", "dealer__name")
    autocomplete_fields = ("user", "dealer")
    readonly_fields = ("full_key", "last_used_at", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("label", "user", "dealer", "is_active")}),
        ("Key", {
            "fields": ("full_key",),
            "description": "Generated on save. Send it as the "
                           "<code>X-API-Key</code> header on every request.",
        }),
        ("Timestamps", {"fields": ("last_used_at", "created_at", "updated_at"),
                        "classes": ("collapse",)}),
    )

    @admin.display(description="API key")
    def full_key(self, obj):
        if not obj.pk:
            return "Save to generate the key."
        return format_html(
            '<code style="font-size:14px;user-select:all;padding:6px 10px;'
            'background:rgba(128,128,128,.15);border-radius:6px;display:inline-block">{}</code>'
            '<p style="margin:6px 0 0;opacity:.7">Copy it now and store it in the app — '
            'anyone holding it can use this account.</p>',
            obj.key,
        )
