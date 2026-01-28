from io import BytesIO

from django.contrib import messages
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .forms import AllocationForm, CustomerForm, InvoiceForm, InvoiceLineFormSet, PaymentForm
from .models import Invoice, Payment, PaymentAllocation, Customer
from .pdf import invoice_pdf_bytes, receipt_pdf_bytes
from .services import create_receipt_for_payment, issue_invoice


def pdf_bytes_to_filelike(b: bytes) -> BytesIO:
    bio = BytesIO(b)
    bio.seek(0)
    return bio


def dashboard(request):
    outstanding = Invoice.objects.filter(status__in=["ISSUED", "PART_PAID"]).order_by("-issue_date")[:10]
    recent_payments = Payment.objects.order_by("-created_at")[:10]
    return render(request, "billing/dashboard.html", {
        "outstanding": outstanding,
        "recent_payments": recent_payments,
    })


def customer_list(request):
    customers = Customer.objects.order_by("name")
    return render(request, "billing/customer_list.html", {"customers": customers})


@require_http_methods(["GET", "POST"])
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Customer created.")
        return redirect("billing:customer_list")
    return render(request, "billing/customer_form.html", {"form": form})


def invoice_list(request):
    invoices = Invoice.objects.select_related("customer").order_by("-created_at")
    return render(request, "billing/invoice_list.html", {"invoices": invoices})


@require_http_methods(["GET", "POST"])
def invoice_create(request):
    invoice = Invoice()
    form = InvoiceForm(request.POST or None, instance=invoice)
    formset = InvoiceLineFormSet(request.POST or None, instance=invoice)

    if request.method == "POST" and form.is_valid() and formset.is_valid():
        invoice = form.save()
        formset.instance = invoice
        formset.save()
        invoice.recompute_totals()
        invoice.save()
        messages.success(request, "Invoice saved as Draft.")
        return redirect("billing:invoice_detail", pk=invoice.pk)

    return render(request, "billing/invoice_form.html", {"form": form, "formset": formset})


def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("customer"), pk=pk)
    invoice.recompute_totals()
    invoice.save(update_fields=["subtotal", "vat", "nhil", "getfund", "total", "updated_at"])
    return render(request, "billing/invoice_detail.html", {"invoice": invoice})


@require_http_methods(["POST"])
def invoice_issue(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    issue_invoice(invoice, actor=request.user if request.user.is_authenticated else None)
    messages.success(request, f"Issued invoice {invoice.invoice_no}.")
    return redirect("billing:invoice_detail", pk=pk)


def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status == "DRAFT":
        messages.error(request, "Issue the invoice before downloading a PDF.")
        return redirect("billing:invoice_detail", pk=pk)

    pdf_bytes = invoice_pdf_bytes(invoice)
    filename = f"{invoice.invoice_no.replace('/', '-')}.pdf"
    return FileResponse(
        pdf_bytes_to_filelike(pdf_bytes),
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )


@require_http_methods(["GET", "POST"])
def payment_create(request):
    form = PaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        payment = form.save()
        messages.success(request, "Payment recorded. Now allocate it to an invoice (optional).")
        return redirect("billing:payment_allocate", pk=payment.pk)
    return render(request, "billing/payment_form.html", {"form": form})


@require_http_methods(["GET", "POST"])
def payment_allocate(request, pk):
    payment = get_object_or_404(Payment.objects.select_related("customer"), pk=pk)

    form = AllocationForm(request.POST or None, customer=payment.customer)
    allocations = list(payment.allocations.select_related("invoice").all())

    allocated_sum = sum((a.amount for a in allocations), 0)
    remaining = payment.amount - allocated_sum

    if request.method == "POST" and form.is_valid():
        invoice = form.cleaned_data["invoice"]
        amount = form.cleaned_data["amount"]

        # guard: cannot allocate more than remaining payment
        if amount > remaining:
            messages.error(request, f"Allocation exceeds remaining payment. Remaining: {remaining:,.2f}")
            return redirect("billing:payment_allocate", pk=pk)

        # guard: cannot allocate more than invoice balance due
        invoice.recompute_totals()
        invoice.save()
        if amount > invoice.balance_due():
            messages.error(request, f"Allocation exceeds invoice balance due ({invoice.balance_due():,.2f}).")
            return redirect("billing:payment_allocate", pk=pk)

        PaymentAllocation.objects.create(payment=payment, invoice=invoice, amount=amount)
        messages.success(request, "Allocation added.")
        return redirect("billing:payment_allocate", pk=pk)

    # refresh allocations display
    allocations = payment.allocations.select_related("invoice").all()
    remaining = payment.amount - sum((a.amount for a in allocations), 0)

    return render(request, "billing/payment_allocate.html", {
        "payment": payment,
        "form": form,
        "allocations": allocations,
        "remaining": remaining,
    })


@require_http_methods(["POST"])
def payment_issue_receipt(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    receipt = create_receipt_for_payment(payment, actor=request.user if request.user.is_authenticated else None)
    messages.success(request, f"Receipt issued: {receipt.receipt_no}")
    return redirect("billing:receipt_detail", pk=receipt.pk)


def receipt_detail(request, pk):
    from .models import Receipt

    receipt = get_object_or_404(Receipt.objects.select_related("payment"), pk=pk)
    return render(request, "billing/receipt_detail.html", {"receipt": receipt})


def receipt_pdf(request, pk):
    from .models import Receipt

    receipt = get_object_or_404(Receipt, pk=pk)
    pdf_bytes = receipt_pdf_bytes(receipt)
    filename = f"{receipt.receipt_no.replace('/', '-')}.pdf"
    return FileResponse(
        pdf_bytes_to_filelike(pdf_bytes),
        as_attachment=True,
        filename=filename,
        content_type="application/pdf",
    )
