from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import Customer, Invoice, InvoiceLine, Payment


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "email", "phone", "address", "tin", "is_vat_withholding_agent"]


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["invoice_type", "customer", "issue_date", "due_date", "notes"]


InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    fields=["description", "qty", "unit_price"],
    extra=1,
    can_delete=True,
)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["customer", "payer_name", "method", "amount", "received_date", "reference"]


class AllocationForm(forms.Form):
    invoice = forms.ModelChoiceField(queryset=Invoice.objects.none())
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))

    def __init__(self, *args, **kwargs):
        customer = kwargs.pop("customer", None)
        super().__init__(*args, **kwargs)
        qs = Invoice.objects.filter(status__in=["ISSUED", "PART_PAID"]).order_by("-issue_date")
        if customer:
            qs = qs.filter(customer=customer)
        self.fields["invoice"].queryset = qs
