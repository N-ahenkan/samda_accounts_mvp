from django.db import transaction

from core.models import AuditLog

from .models import Invoice, Receipt


@transaction.atomic
def issue_invoice(invoice: Invoice, actor=None):
    if invoice.status != Invoice.Status.DRAFT:
        return invoice

    invoice.assign_number_if_needed()
    invoice.recompute_totals()
    invoice.status = Invoice.Status.ISSUED
    invoice.save()

    AuditLog.objects.create(
        actor=actor,
        action="INVOICE_ISSUED",
        object_type="Invoice",
        object_id=str(invoice.pk),
        message=f"Issued {invoice.invoice_no}",
    )
    return invoice


@transaction.atomic
def create_receipt_for_payment(payment, actor=None):
    if hasattr(payment, "receipt"):
        return payment.receipt

    receipt = Receipt(payment=payment)
    receipt.assign_number_if_needed()
    receipt.save()

    for alloc in payment.allocations.select_related("invoice"):
        inv = alloc.invoice
        inv.recompute_totals()
        bal = inv.balance_due()
        if bal <= 0:
            inv.status = Invoice.Status.PAID
        else:
            inv.status = Invoice.Status.PART_PAID
        inv.save()

    AuditLog.objects.create(
        actor=actor,
        action="RECEIPT_ISSUED",
        object_type="Receipt",
        object_id=str(receipt.pk),
        message=f"Issued {receipt.receipt_no} for payment {payment.pk}",
    )

    return receipt
