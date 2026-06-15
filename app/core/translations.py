# KastomPOS Translations Catalog

TRANSLATIONS = {
    "sw": {
        "Home": "Nyumbani",
        "Dashboard": "Dashibodi",
        "POS": "POS",
        "Billing": "Ankara",
        "Bookings": "Uhifadhi",
        "Bookings Calendar": "Kalenda ya Uhifadhi",
        "Room Bookings": "Uhifadhi wa Vyumba",
        "Inventory": "Stoki / Bidhaa",
        "Supplier Management": "Wasambazaji",
        "Reports": "Ripoti",
        "Cashier Report": "Ripoti ya Keshia",
        "Open Sales": "Mauzo Wazi",
        "Logout": "Ondoka",
        "Search": "Tafuta",
        "Language": "Lugha",
        "Version": "Toleo",
        "Grand Total": "Jumla Kuu",
        "Amount Paid": "Kiasi Kilicholipwa",
        "Change/Balance": "Chenji/Salio",
        "Process Order": "Tekeleza Agizo",
        "Settings": "Mipangilio",
        "Room Bookings Calendar": "Kalenda ya Uhifadhi",
        "Online Bookings": "Uhifadhi wa Mtandaoni",
        "Book Room": "Hifadhi Chumba",
        "Notifications": "Taarifa",
        "See All Notifications": "Angalia Taarifa Zote",
        "My Profile": "Wasifu Wangu"
    }
}

def translate(text: str, lang: str = "en") -> str:
    """Translate a text string into the selected language."""
    if lang == "sw":
        return TRANSLATIONS["sw"].get(text, text)
    return text
