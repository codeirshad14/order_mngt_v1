from django.contrib import admin
from django.utils.html import format_html

from .forms import BankDetailForm
from .models import BankDetail

# Register your models here.


@admin.register(BankDetail)
class BankDetailAdmin(admin.ModelAdmin):
    form = BankDetailForm
    list_display = ("bank_name", "label", "account_name", "masked_account",
                    "ifsc", "account_type", "is_primary")
    list_filter = ("is_primary", "account_type", "bank_name")
    list_editable = ("is_primary",)
    search_fields = ("bank_name", "account_name", "account_number", "ifsc", "upi_id")
    readonly_fields = ("qr_preview", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("label", "is_primary")}),
        ("Account", {"fields": ("account_name", "account_number", "account_type")}),
        ("Bank", {"fields": ("bank_name", "branch", "ifsc", "micr", "swift")}),
        ("UPI", {
            "fields": ("upi_id", "upi_qr", "qr_preview"),
            "description": "Upload the QR image saved from your UPI app.",
        }),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="QR preview")
    def qr_preview(self, obj):
        if not obj.upi_qr:
            return "No QR uploaded yet."
        return format_html(
            '<img src="{}" style="width:180px;height:180px;object-fit:contain;'
            'background:#fff;padding:8px;border:1px solid #ddd;border-radius:8px">',
            obj.upi_qr.url,
        )
