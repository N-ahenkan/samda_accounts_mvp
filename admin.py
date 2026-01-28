from django.contrib import admin

from .models import (
    Customer,
    DocumentSequence,
    Invoice,
    InvoiceLine,
    Payment,
    PaymentAllocation,
    Receipt,
)


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_no", "invoice_type", "customer", "status", "issue_date", "total")
    list_filter = ("invoice_type", "status")
    search_fields = ("invoice_no", "customer__name")
    inlines = [InvoiceLineInline]


admin.site.register(Customer)
admin.site.register(Payment)
admin.site.register(PaymentAllocation)
admin.site.register(Receipt)
admin.site.register(DocumentSequence)
