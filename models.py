from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from core.models import TimeStampedModel, TaxProfile


class Customer(TimeStampedModel):
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=40, blank=True, default="")
    address = models.TextField(blank=True, default="")
    tin = models.CharField(max_length=60, blank=True, default="")
    is_vat_withholding_agent = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class DocumentSequence(models.Model):
    key = models.CharField(max_length=40, unique=True)  # INV_NONVAT, INV_VAT, RECEIPT
    prefix = models.CharField(max_length=40, default="SAMDA/")
    next_number = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.key} -> {self.prefix}{self.next_number:06d}"

    @classmethod
    def next(cls, key: str) -> str:
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(
                key=key,
                defaults={"prefix": "SAMDA/", "next_number": 1},
            )
            number = seq.next_number
            seq.next_number += 1
            seq.save(update_fields=["next_number"])
        return f"{seq.prefix}{number:06d}"


class Invoice(TimeStampedModel):
    class InvoiceType(models.TextChoices):
        VAT = "VAT", "VAT Invoice"
        NONVAT = "NONVAT", "Non-VAT Invoice"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        PART_PAID = "PART_PAID", "Part-Paid"
        PAID = "PAID", "Paid"
        VOID = "VOID", "Void"

    invoice_type = models.CharField(max_length=10, choices=InvoiceType.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)

    invoice_no = models.CharField(max_length=60, unique=True, blank=True, default="")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")

    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)

    tax_profile = models.ForeignKey(TaxProfile, on_delete=models.PROTECT, null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    vat = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    nhil = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    getfund = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def __str__(self):
        return self.invoice_no or f"Invoice({self.pk})"

    def assign_number_if_needed(self):
        if self.invoice_no:
            return
        if self.invoice_type == self.InvoiceType.VAT:
            self.invoice_no = DocumentSequence.next("INV_VAT")
        else:
            self.invoice_no = DocumentSequence.next("INV_NONVAT")

    def recompute_totals(self):
        lines = list(self.lines.all())
        subtotal = sum((ln.line_total() for ln in lines), Decimal("0.00"))

        vat = nhil = getfund = Decimal("0.00")
        if self.invoice_type == self.InvoiceType.VAT:
            tp = self.tax_profile or TaxProfile.objects.filter(is_active=True).order_by("-effective_from").first()
            if tp:
                vat = (subtotal * tp.vat_rate).quantize(Decimal("0.01"))
                nhil = (subtotal * tp.nhil_rate).quantize(Decimal("0.01"))
                getfund = (subtotal * tp.getfund_rate).quantize(Decimal("0.01"))

        total = (subtotal + vat + nhil + getfund).quantize(Decimal("0.01"))

        self.subtotal = subtotal.quantize(Decimal("0.01"))
        self.vat = vat
        self.nhil = nhil
        self.getfund = getfund
        self.total = total

    def amount_paid(self):
        return sum((alloc.amount for alloc in self.allocations.all()), Decimal("0.00"))

    def balance_due(self):
        return (self.total - self.amount_paid()).quantize(Decimal("0.01"))


class InvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=250)
    qty = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    def line_total(self):
        return (self.qty * self.unit_price).quantize(Decimal("0.01"))


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "CASH", "Cash"
        MOMO = "MOMO", "Mobile Money"
        BANK = "BANK", "Bank Transfer"
        CHEQUE = "CHEQUE", "Cheque"

    payer_name = models.CharField(max_length=200)
    method = models.CharField(max_length=10, choices=Method.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    received_date = models.DateField(default=timezone.now)
    reference = models.CharField(max_length=120, blank=True, default="")
    customer = models.ForeignKey(Customer, null=True, blank=True, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.payer_name} {self.amount} {self.received_date}"


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="allocations")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=12, decimal_places=2)


class Receipt(TimeStampedModel):
    receipt_no = models.CharField(max_length=60, unique=True, blank=True, default="")
    payment = models.OneToOneField(Payment, on_delete=models.PROTECT, related_name="receipt")
    issued_date = models.DateField(default=timezone.now)

    def assign_number_if_needed(self):
        if not self.receipt_no:
            self.receipt_no = DocumentSequence.next("RECEIPT")

    def __str__(self):
        return self.receipt_no or f"Receipt({self.pk})"
