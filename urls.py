from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),

    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/new/", views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/issue/", views.invoice_issue, name="invoice_issue"),
    path("invoices/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),

    path("payments/new/", views.payment_create, name="payment_create"),
    path("payments/<int:pk>/allocate/", views.payment_allocate, name="payment_allocate"),
    path("payments/<int:pk>/issue-receipt/", views.payment_issue_receipt, name="payment_issue_receipt"),

    path("receipts/<int:pk>/", views.receipt_detail, name="receipt_detail"),
    path("receipts/<int:pk>/pdf/", views.receipt_pdf, name="receipt_pdf"),
]
