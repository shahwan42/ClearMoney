"""Seed SystemBank records for Egypt — 20 banks/fintechs/wallets.

Idempotent — safe to re-run. Keyed on (country, short_name).

Reuses existing SVG assets in static/img/institutions/ where present
and writes fallback SVGs (rect + short_name text) for any missing logos
(see static/img/institutions/{standard-chartered,blom,instapay,union-bank}.svg).
"""

from django.db import migrations

EGYPT_BANKS = [
    # (short_name, name_en, name_ar, brand_color, bank_type, svg_filename)
    (
        "CIB",
        "Commercial International Bank",
        "البنك التجاري الدولي",
        "#003366",
        "bank",
        "cib.svg",
    ),
    (
        "NBE",
        "National Bank of Egypt",
        "البنك الأهلي المصري",
        "#1a4d2e",
        "bank",
        "nbe.svg",
    ),
    ("Banque Misr", "Banque Misr", "بنك مصر", "#8b0000", "bank", "banque-misr.svg"),
    ("QNB", "QNB Alahli", "بنك قطر الوطني الأهلي", "#5c0057", "bank", "qnb.png"),
    ("HSBC", "HSBC Egypt", "بنك HSBC مصر", "#db0011", "bank", "hsbc.svg"),
    (
        "SCB",
        "Standard Chartered Egypt",
        "ستاندرد تشارترد مصر",
        "#0072aa",
        "bank",
        "standard-chartered.svg",
    ),
    (
        "Faisal",
        "Faisal Islamic Bank",
        "بنك فيصل الإسلامي",
        "#006600",
        "bank",
        "faisal-islamic.svg",
    ),
    (
        "ABK",
        "Al Ahli Bank of Kuwait",
        "البنك الأهلي الكويتي",
        "#003580",
        "bank",
        "abk.svg",
    ),
    (
        "Mashreq",
        "Mashreq Bank Egypt",
        "بنك المشرق مصر",
        "#e60028",
        "bank",
        "mashreq.svg",
    ),
    (
        "AAIB",
        "Arab African International Bank",
        "البنك العربي الأفريقي الدولي",
        "#004b87",
        "bank",
        "aaib.svg",
    ),
    (
        "EGB",
        "Egyptian Gulf Bank",
        "بنك الخليج المصري",
        "#006b9e",
        "bank",
        "eg-bank.svg",
    ),
    (
        "Suez Canal",
        "Suez Canal Bank",
        "بنك قناة السويس",
        "#00457c",
        "bank",
        "suez-canal.png",
    ),
    ("Blom", "Blom Bank Egypt", "بنك بلوم مصر", "#c8102e", "bank", "blom.svg"),
    (
        "Crédit Agricole",
        "Crédit Agricole Egypt",
        "كريدي أجريكول مصر",
        "#008000",
        "bank",
        "credit-agricole.svg",
    ),
    (
        "ADIB",
        "Abu Dhabi Islamic Bank Egypt",
        "بنك أبوظبي الإسلامي مصر",
        "#8b6914",
        "bank",
        "adib.png",
    ),
    (
        "Arab Bank",
        "Arab Bank Egypt",
        "البنك العربي مصر",
        "#004f9f",
        "bank",
        "arab-bank.svg",
    ),
    (
        "Union",
        "Union National Bank Egypt",
        "البنك الوطني المتحد مصر",
        "#003087",
        "bank",
        "union-bank.svg",
    ),
    (
        "Attijariwafa",
        "Attijariwafa Bank Egypt",
        "بنك التجاري وفا مصر",
        "#e2001a",
        "bank",
        "attijariwafa.png",
    ),
    ("InstaPay", "InstaPay", "إنستاباي", "#6c0091", "fintech", "instapay.svg"),
    (
        "Vodafone Cash",
        "Vodafone Cash",
        "فودافون كاش",
        "#e60000",
        "wallet",
        "vodafone-cash.svg",
    ),
]


def seed_banks(apps, schema_editor):  # type: ignore[no-untyped-def]
    SystemBank = apps.get_model("accounts", "SystemBank")
    for order, row in enumerate(EGYPT_BANKS, start=1):
        short_name, name_en, name_ar, color, bank_type, svg_file = row
        SystemBank.objects.update_or_create(
            country="EG",
            short_name=short_name,
            defaults={
                "name": {"en": name_en, "ar": name_ar},
                "svg_path": f"img/institutions/{svg_file}",
                "brand_color": color,
                "bank_type": bank_type,
                "is_active": True,
                "display_order": order,
            },
        )


def unseed_banks(apps, schema_editor):  # type: ignore[no-untyped-def]
    SystemBank = apps.get_model("accounts", "SystemBank")
    SystemBank.objects.filter(
        country="EG",
        short_name__in=[row[0] for row in EGYPT_BANKS],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_systembank"),
    ]

    operations = [
        migrations.RunPython(seed_banks, unseed_banks),
    ]
