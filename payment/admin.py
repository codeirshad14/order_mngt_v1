from django.contrib import admin

from .models import Payment

# Register your models here.


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("receipt_no", "dealer", "against", "paid_on", "mode", "reference", "amount")
    list_filter = ("mode", "paid_on", "dealer")
    search_fields = ("receipt_no", "reference", "dealer__name", "order__order_no")
    autocomplete_fields = ("dealer", "order")
    readonly_fields = ("receipt_no", "created_at", "updated_at")
    date_hierarchy = "paid_on"

    fieldsets = (
        (None, {"fields": ("receipt_no", "dealer", "order"),
                "description": "Leave the order empty to record an advance payment."}),
        ("Amount", {"fields": ("amount", "paid_on", "mode", "reference", "note")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(description="Against")
    def against(self, obj):
        return obj.against
