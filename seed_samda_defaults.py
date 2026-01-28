from datetime import date

from django.core.management.base import BaseCommand

from core.models import TaxProfile
from billing.models import DocumentSequence


class Command(BaseCommand):
    help = "Seed default SAMDA tax profile and document sequences."

    def handle(self, *args, **options):
        tp, created = TaxProfile.objects.get_or_create(
            effective_from=date(2026, 1, 1),
            defaults={
                "name": "Ghana VAT Standard (MVP)",
                "vat_rate": 0.1500,
                "nhil_rate": 0.0250,
                "getfund_rate": 0.0250,
                "is_active": True,
            },
        )
        if not created:
            tp.is_active = True
            tp.save(update_fields=["is_active"])
        self.stdout.write(self.style.SUCCESS(f"TaxProfile ready: {tp}"))

        sequences = [
            ("INV_VAT", "SAMDA/VAT/"),
            ("INV_NONVAT", "SAMDA/INV/"),
            ("RECEIPT", "SAMDA/RCT/"),
        ]
        for key, prefix in sequences:
            seq, _ = DocumentSequence.objects.get_or_create(
                key=key,
                defaults={"prefix": prefix, "next_number": 1},
            )
            if seq.prefix != prefix:
                seq.prefix = prefix
                seq.save(update_fields=["prefix"])
            self.stdout.write(self.style.SUCCESS(f"Sequence ready: {key} -> {prefix}{seq.next_number:06d}"))

        self.stdout.write(self.style.SUCCESS("Seed completed."))
