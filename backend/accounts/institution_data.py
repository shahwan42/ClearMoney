"""
Static preset data for Egyptian banks, fintechs, and wallet examples.

Used by the institution creation form to offer a searchable combobox of
known institutions with pre-set name, icon filename, and brand color.

Fields per preset:
- name  : display label shown in the combobox, formatted as "ABBR - Full Name"
          for banks (e.g. "BM - Banque Misr"), or plain name for fintechs/wallets
- value : what gets stored in the DB — the short official abbreviation
          (e.g. "BM", "CIB"). Omitted when the name is already concise;
          the JS falls back to name in that case.
- icon  : filename (e.g. "cib.svg") → image in static/img/institutions/
          OR emoji string (e.g. "👛") → rendered directly as text
- color : brand hex color

The institution_display_name template filter reverses value → name so the
full descriptive name is shown in the UI even though only the abbreviation
is stored in the DB.

Bank list sourced from the Central Bank of Egypt (CBE) registry.
Abbreviations verified against CBE documents, SWIFT codes, and official
bank websites. Colors verified against official brand identities.
"""

# ---------------------------------------------------------------------------
# Egyptian banks — icon is an SVG/PNG filename in static/img/institutions/
# ---------------------------------------------------------------------------

EGYPTIAN_BANKS: list[dict[str, str]] = [
    # ── Public / state-owned ─────────────────────────────────────────────
    {
        "name": "NBE - National Bank of Egypt",
        "value": "NBE",
        "icon": "nbe.svg",
        "color": "#006643",
    },
    {
        "name": "BM - Banque Misr",
        "value": "BM",
        "icon": "banque-misr.svg",
        "color": "#871E35",
    },
    {
        "name": "BdC - Banque du Caire",
        "value": "BdC",
        "icon": "banque-du-caire.svg",
        "color": "#F68B1F",
    },
    {
        "name": "ABE - Agricultural Bank of Egypt",
        "value": "ABE",
        "icon": "abe.png",
        "color": "#2E7D32",
    },
    {
        "name": "HDB - Housing and Development Bank",
        "value": "HDB",
        "icon": "hdb.svg",
        "color": "#002F5F",
    },
    {
        "name": "EDBE - Export Development Bank of Egypt",
        "value": "EDBE",
        "icon": "edbe.svg",
        "color": "#003F7F",
    },
    {
        "name": "EALB - Egyptian Arab Land Bank",
        "value": "EALB",
        "icon": "ealb.png",
        "color": "#1A5276",
    },
    {
        "name": "United Bank",
        "value": "UB",
        "icon": "united-bank.svg",
        "color": "#0050A0",
    },
    # ── Private Egyptian ─────────────────────────────────────────────────
    {
        "name": "CIB - Commercial International Bank",
        "value": "CIB",
        "icon": "cib.svg",
        "color": "#003DA5",
    },
    {
        "name": "EG Bank - Egyptian Gulf Bank",
        "value": "EG Bank",
        "icon": "eg-bank.svg",
        "color": "#003B70",
    },
    {
        "name": "AAIB - Arab African International Bank",
        "value": "AAIB",
        "icon": "aaib.svg",
        "color": "#1B6936",
    },
    {
        "name": "Faisal Islamic Bank",
        "value": "FIBE",
        "icon": "faisal-islamic.svg",
        "color": "#07641D",
    },
    {
        "name": "Suez Canal Bank",
        "value": "SCB",
        "icon": "suez-canal.png",
        "color": "#0066CC",
    },
    {
        "name": "SAIB - Société Arabe Internationale de Banque",
        "value": "SAIB",
        "icon": "saib.svg",
        "color": "#004B87",
    },
    {
        "name": "AIB - Arab International Bank",
        "value": "AIB",
        "icon": "aib.png",
        "color": "#004080",
    },
    {
        "name": "MIDBank - Misr Iran Development Bank",
        "value": "MIDBank",
        "icon": "midbank.svg",
        "color": "#1B4F72",
    },
    # ── Regional / Arab ──────────────────────────────────────────────────
    {
        "name": "QNB - Qatar National Bank",
        "value": "QNB",
        "icon": "qnb.png",
        "color": "#0060AE",
    },
    {
        "name": "ADIB - Abu Dhabi Islamic Bank",
        "value": "ADIB",
        "icon": "adib.png",
        "color": "#002F69",
    },
    {
        "name": "ADCB Egypt - Abu Dhabi Commercial Bank",
        "value": "ADCB",
        "icon": "adcb.png",
        "color": "#ED1C24",
    },
    {
        "name": "FAB Misr - First Abu Dhabi Bank",
        "value": "FAB Misr",
        "icon": "fab-misr.svg",
        "color": "#002B74",
    },
    {
        "name": "Emirates NBD Egypt",
        "value": "Emirates NBD",
        "icon": "emirates-nbd.svg",
        "color": "#072447",
    },
    {
        "name": "KFH-Egypt - Kuwait Finance House",
        "value": "KFH Egypt",
        "icon": "kfh-egypt.png",
        "color": "#006633",
    },
    {
        "name": "NBK - National Bank of Kuwait Egypt",
        "value": "NBK Egypt",
        "icon": "nbk.svg",
        "color": "#001F5B",
    },
    {
        "name": "ABK - Al Ahli Bank of Kuwait Egypt",
        "value": "ABK Egypt",
        "icon": "abk.svg",
        "color": "#00485F",
    },
    {
        "name": "Al Baraka Bank Egypt",
        "value": "Al Baraka",
        "icon": "al-baraka.png",
        "color": "#FF5800",
    },
    {
        "name": "Arab Bank Egypt",
        "value": "Arab Bank",
        "icon": "arab-bank.svg",
        "color": "#002B5B",
    },
    {
        "name": "Bank ABC Egypt - Arab Banking Corporation",
        "value": "Bank ABC",
        "icon": "bank-abc.png",
        "color": "#003366",
    },
    {
        "name": "Attijariwafa Bank Egypt",
        "value": "Attijariwafa",
        "icon": "attijariwafa.png",
        "color": "#E30613",
    },
    # ── International ────────────────────────────────────────────────────
    {"name": "HSBC Egypt", "value": "HSBC", "icon": "hsbc.svg", "color": "#DB0011"},
    {"name": "Alex Bank", "icon": "alex-bank.svg", "color": "#0B4A35"},
    {
        "name": "Credit Agricole Egypt",
        "value": "CAE",
        "icon": "credit-agricole.svg",
        "color": "#86CE00",
    },
    {
        "name": "Citibank Egypt",
        "value": "Citi",
        "icon": "citibank.svg",
        "color": "#003B70",
    },
    {
        "name": "Mashreq Bank Egypt",
        "value": "Mashreq",
        "icon": "mashreq.svg",
        "color": "#E31837",
    },
    {"name": "Bank NXT", "icon": "bank-nxt.png", "color": "#005B9A"},
]

# ---------------------------------------------------------------------------
# Egyptian fintechs — icon is an SVG/PNG filename in static/img/institutions/
# ---------------------------------------------------------------------------

EGYPTIAN_FINTECHS: list[dict[str, str]] = [
    # ── Payments & Super-apps ────────────────────────────────────────────────
    {"name": "Fawry", "icon": "fawry.png", "color": "#FF6600"},
    {"name": "Aman", "icon": "aman.png", "color": "#0A3D62"},
    # ── BNPL & Installments ──────────────────────────────────────────────────
    {"name": "ValU", "icon": "valu.svg", "color": "#FF6B35"},
    {"name": "Forsa", "icon": "forsa.png", "color": "#1E40AF"},
    {"name": "Souhoola", "icon": "souhoola.svg", "color": "#7001E4"},
    {"name": "Contact Financial", "icon": "contact.png", "color": "#E30613"},
    {"name": "Takka", "icon": "takka.png", "color": "#2C3E7A"},
    {"name": "MID Takseet", "icon": "mid-takseet.png", "color": "#004B87"},
    # ── Savings & Community ──────────────────────────────────────────────────
    {"name": "MoneyFellows", "icon": "money-fellows.png", "color": "#1B3D6E"},
    {"name": "MNT Halan", "icon": "mnt-halan.svg", "color": "#1ED58C"},
    {"name": "Mylo", "icon": "mylo.png", "color": "#4B2D83"},
    # ── Digital Banking ──────────────────────────────────────────────────────
    {"name": "Telda", "icon": "telda.svg", "color": "#6C63FF"},
    {"name": "Khazna", "icon": "khazna.svg", "color": "#1A73E8"},
    {"name": "TRU", "icon": "tru.svg", "color": "#2B3497"},
    {"name": "Kash", "icon": "kash.svg", "color": "#00C853"},
    {"name": "Lucky", "icon": "lucky.svg", "color": "#FFD700"},
]

# ---------------------------------------------------------------------------
# Wallet examples — physical use emoji, digital use SVG/PNG filename
# ---------------------------------------------------------------------------

WALLET_EXAMPLES: list[dict[str, str]] = [
    # Physical wallets — rendered as emoji, no image file needed
    {"name": "Pocket Wallet", "icon": "👛", "color": "#8B5E3C", "group": "physical"},
    {"name": "Cross Bag", "icon": "👜", "color": "#6B4C3B", "group": "physical"},
    {"name": "Backpack", "icon": "🎒", "color": "#4A6741", "group": "physical"},
    {"name": "Desk Drawer", "icon": "🗄️", "color": "#7C7C7C", "group": "physical"},
    {"name": "Safe", "icon": "🔐", "color": "#3D3D3D", "group": "physical"},
    {"name": "Envelope", "icon": "✉️", "color": "#C4A35A", "group": "physical"},
    {"name": "Car Console", "icon": "🚗", "color": "#2C5F8A", "group": "physical"},
    # Digital wallets — icon is an SVG/PNG filename in static/img/institutions/
    {
        "name": "Vodafone Cash",
        "icon": "vodafone-cash.svg",
        "color": "#E60000",
        "group": "digital",
    },
    {
        "name": "e& money",
        "icon": "etisalat-cash.svg",
        "color": "#E00B14",
        "group": "digital",
    },
    {
        "name": "Orange Money",
        "icon": "orange-cash.svg",
        "color": "#FF7900",
        "group": "digital",
    },
    {"name": "WE Pay", "icon": "we-pay.svg", "color": "#5B2C91", "group": "digital"},
]


# ---------------------------------------------------------------------------
# Reverse lookup: stored DB value → full display name
# e.g. "CIB" → "CIB - Commercial International Bank", "BM" → "Banque Misr"
# Built once at import time from all preset lists.
# ---------------------------------------------------------------------------

_all_presets = EGYPTIAN_BANKS + EGYPTIAN_FINTECHS + WALLET_EXAMPLES
PRESET_DISPLAY_NAMES: dict[str, str] = {
    p.get("value", p["name"]): p["name"] for p in _all_presets
}


def get_display_name(stored_name: str) -> str:
    """Return the full display name for a stored institution name.

    Falls back to the stored name itself for custom (non-preset) institutions.
    """
    return PRESET_DISPLAY_NAMES.get(stored_name, stored_name)
