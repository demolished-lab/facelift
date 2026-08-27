"""Market profiles: pricing, language, legal basis, sender identity, caps.

PRD FR-5.2 (jurisdiction engine) and FR-6.1 (catalog) read from here.
Sender identity per owner decision 2026-08-23; address_line and privacy_url
MUST be filled before any send is possible (SECURITY-AUDIT F4/F12 gates).
"""

MARKETS = {
    "in": {
        "label": "India",
        "currency": "INR",
        "language": "en-IN",
        "packages": {"starter": 7999, "growth": 14999, "pro": 29999},
        "care_monthly": 999,
        "legal_basis": "dpdp_7a_voluntarily_published",
        "sender": {
            "email": "operator@example.com",
            "name": "Raja - Facelift",
            "address_line": "ADDRESS_LINE",
            "privacy_url": "https://facelift-privacy.facelift.workers.dev/",
        },
        "daily_caps": {"discover": 500, "audit": 75, "send": 30},
    },
    "us": {
        "label": "United States",
        "currency": "USD",
        "language": "en-US",
        "packages": {"starter": 750, "growth": 1500, "pro": 3000},
        "care_monthly": 79,
        "legal_basis": "can_spam_optout",
        "sender": {
            "email": "operator@example.com",
            "name": "Raja - Facelift",
            "address_line": "ADDRESS_LINE",
            "privacy_url": "https://facelift-privacy.facelift.workers.dev/",
        },
        "daily_caps": {"discover": 500, "audit": 75, "send": 30},
    },
}

PROFILE_ROADMAP = ["uk", "au"]
BLOCKED_PROFILES = ["de", "ca"]

# Vertical intelligence: purpose + must/scaling features per trade.
# Detection scans extraction services/tagline against these keys.
VERTICAL_PROFILES = {
    "hostel": {
        "match": ("hostel", "guest house", "guesthouse", "stay", "rooms",
                  "dormitor", "hotel", "lodge"),
        "purpose": "lodging - guests compare rooms, safety and location, then inquire",
        "must": [
            "Room types with photos (from provided images only)",
            "Amenities list from Facts.services verbatim",
            "Location card with directions link (Google Maps share URL)",
            "Booking INQUIRY flow: prefilled WhatsApp (wa.me/<phone>) AND "
            "mailto fallback - zero backend needed",
            "Check-in/out or front-desk hours if present in Facts.hours",
        ],
        "scaling": [
            "Seasonal offers block (owner-editable later)",
            "Reviews/testimonials section scaffold (filled post-sale)",
            "Multi-language toggle-ready structure",
        ],
        "playbook": {
            "sections": [
                "HERO: room-scene image, name, one-line promise, "
                "'Check availability' CTA",
                "ROOMS: 3 room-type cards (photo, beds, from-price marked "
                "TODO-OWNER, 'Select' button)",
                "AMENITIES: icon row from Facts.services",
                "LOCATION: address card + embedded map + distances to "
                "station/attractions if known",
                "STAY FAQ: check-in time, visitors, luggage, parking "
                "(sensible defaults, each marked 'confirm')",
                "INQUIRY BAND: big WhatsApp CTA + phone + email fallback",
            ],
            "signature": "Room-selector: tapping a room type + dates "
            "composes a structured WhatsApp booking inquiry "
            "('Hi! I'd like the <room> for <dates> - available?')",
            "voice": "warm, safety-conscious, local-guide tone; short "
            "sentences a tired traveler skims",
        },
    },
    "restaurant": {
        "match": ("restaurant", "cafe", "food", "menu", "kitchen", "tiffin",
                  "bakery", "sweets", "dining"),
        "purpose": "food business - diners check menu, hours and how to reach/order",
        "must": [
            "Menu/highlights section derived ONLY from Facts.services",
            "Opening hours prominent (from Facts.hours)",
            "Directions link + tap-to-call + prefilled WhatsApp order/reservation",
        ],
        "scaling": [
            "Daily-specials strip (owner-editable)",
            "Delivery-partner links row (Swiggy/Zomato if ever provided)",
        ],
        "playbook": {
            "sections": [
                "HERO: appetizing food shot, name, cuisine tagline, "
                "'View menu' + 'Reserve' CTAs",
                "MENU: category tabs or grid with item cards - prices "
                "marked TODO-OWNER",
                "HOURS + LOCATION: prominent card, today's status "
                "(open/closed computed client-side)",
                "GALLERY: food/interior photos",
                "RESERVE/ORDER BAND: WhatsApp composer + call + directions",
                "REVIEWS scaffold: 'What guests say' (post-sale fill)",
            ],
            "signature": "Tap-to-order basket: tapping dishes composes a "
            "prefilled WhatsApp order message ('2x Masala Dosa, 1x Filter "
            "coffee - pickup at 7pm?')",
            "voice": "appetizing, local pride, zero fluff - write like a "
            "favorite food writer, not a brochure",
        },
    },
    "clinic": {
        "match": ("clinic", "dentist", "doctor", "medical", "pharmacy",
                  "health", "diagnostic"),
        "purpose": "healthcare - patients verify credibility, timings and booking path",
        "must": [
            "Credentials/specialties section strictly from Facts",
            "Consultation hours prominent",
            "Appointment request via prefilled WhatsApp + mailto",
            "Emergency contact emphasized if any phone exists",
        ],
        "scaling": [
            "Health-tips blog scaffold",
            "Insurance/partners row (post-sale data only)",
        ],
        "playbook": {
            "sections": [
                "HERO: calm clinic imagery, name, specialty line, "
                "'Book appointment' CTA",
                "SPECIALTIES grid from Facts.services with plain-language "
                "descriptions",
                "TIMINGS table incl. holiday note",
                "DOCTOR/ABOUT card (only Facts-sourced credentials)",
                "APPOINTMENT band: structured WhatsApp composer "
                "(dept + preferred day)",
                "PATIENT FAQ: what to bring, payment modes, parking",
            ],
            "signature": "Appointment composer: pick concern + day -> "
            "structured WhatsApp request ('Appointment request: <concern>, "
            "<day> - name will follow')",
            "voice": "calm, credentialed, reassuring - never salesy; "
            "clarity over persuasion",
        },
    },
    "fitness": {
        "match": ("gym", "fitness", "sports", "yoga", "training"),
        "purpose": "fitness business - prospects compare plans, trainers, results",
        "must": [
            "Plans/membership grid derived from Facts.services",
            "Schedule/timings block",
            "Trial-session CTA via prefilled WhatsApp",
        ],
        "scaling": ["Trainer profiles scaffold", "Transformation gallery"],
        "playbook": {
            "sections": [
                "HERO: gym-floor energy shot, name, promise, 'Claim free "
                "trial' CTA",
                "PLANS: 3-column comparator (monthly/quarterly/annual) - "
                "prices TODO-OWNER",
                "SCHEDULE: weekly class timetable",
                "FACILITIES icon grid from Facts.services",
                "TRIAL BAND: WhatsApp composer ('Trial claim - <plan>')",
                "RESULTS scaffold: transformations/testimonials post-sale",
            ],
            "signature": "Plan comparator toggle + one-tap trial claim "
            "composing WhatsApp message with selected plan",
            "voice": "energetic, no-excuses, second person - 'you', never "
            "'we offer'",
        },
    },
    "salon": {
        "match": ("salon", "beauty", "hair", "spa"),
        "purpose": "beauty services - clients browse services and book appointments",
        "must": [
            "Service price-list layout from Facts.services",
            "Before/after gallery slots using provided photos",
            "Appointment CTA via prefilled WhatsApp",
        ],
        "scaling": ["Offers banner", "Loyalty/referral block"],
        "playbook": {
            "sections": [
                "HERO: styled interior/look shot, name, signature-service "
                "line, 'Book' CTA",
                "SERVICES price-list with duration column (prices "
                "TODO-OWNER)",
                "GALLERY: looks/work shots",
                "TEAM/ABOUT card if names exist in Facts",
                "BOOKING band: service picker -> WhatsApp composer",
                "AFTER-CARE notes block",
            ],
            "signature": "Service picker: select services -> composed "
            "WhatsApp appointment request with list + preferred time",
            "voice": "stylish, pampering, confident - beauty-editor tone",
        },
    },
}
DEFAULT_PROFILE = {
    "purpose": "local business - visitors need trust, offer and a one-tap way to act",
    "must": [
        "Services section from Facts.services verbatim",
        "Tap-to-call, prefilled WhatsApp inquiry, directions link",
        "Hours/address card",
    ],
    "scaling": ["Testimonials scaffold", "FAQ block"],
    "playbook": {
        "sections": [
            "HERO: best available imagery or rich typographic treatment",
            "OFFER: services/products grid from Facts.services with "
            "TODO-OWNER price slots",
            "TRUST: hours, address card, map link, any review snippets "
            "from Facts only",
            "INQUIRY BAND: WhatsApp + call + directions one-tap row",
            "FAQ: 4-5 questions customers actually ask this trade",
        ],
        "signature": "Inquiry composer: visitor picks what they want -> "
        "structured prefilled WhatsApp/mailto message",
        "voice": "clear, honest, locally rooted - plain words that build "
        "trust fast",
    },
}


def detect_vertical(text: str) -> dict:
    low = (text or "").lower()
    best_key, hits = None, 0
    for key, prof in VERTICAL_PROFILES.items():
        n = sum(1 for kw in prof["match"] if kw in low)
        if n > hits:
            best_key, hits = key, n
    return VERTICAL_PROFILES.get(best_key, DEFAULT_PROFILE)


BRAND = "Facelift"
DOMAIN_LABEL_CANDIDATE = "facelift.dpdns.org"

CITY_BOXES_IN = {
    "delhi": (28.40, 76.90, 28.90, 77.35),
    "mumbai": (18.90, 72.78, 19.30, 73.05),
    "bangalore": (12.85, 77.45, 13.15, 77.75),
    "hyderabad": (17.25, 78.30, 17.60, 78.60),
    "chennai": (12.90, 80.15, 13.25, 80.35),
    "pune": (18.45, 73.75, 18.65, 74.00),
    "ahmedabad": (22.95, 72.50, 23.10, 72.70),
    "jaipur": (26.80, 75.70, 27.00, 75.90),
    "lucknow": (26.75, 80.85, 27.00, 81.05),
    "kanpur": (26.38, 80.28, 26.55, 80.42),
    "nagpur": (21.10, 79.00, 21.25, 79.18),
    "indore": (22.65, 75.80, 22.82, 75.95),
    "bhopal": (23.20, 77.35, 23.32, 77.48),
    "patna": (25.55, 85.05, 25.68, 85.20),
    "kochi": (9.90, 76.24, 10.05, 76.34),
    "coimbatore": (10.95, 76.90, 11.08, 77.06),
    "surat": (21.15, 72.78, 21.25, 72.88),
    "varanasi": (25.26, 82.94, 25.36, 83.05),
    "amritsar": (31.58, 74.82, 31.68, 74.92),
    "chandigarh": (30.68, 76.72, 30.80, 76.85),
}

VERTICAL_AMENITIES = (
    "restaurant", "cafe", "fast_food", "bar",
    "clinic", "dentist", "pharmacy", "doctors",
    "hotel", "guest_house", "hostel",
    "gym", "sports_centre",
    "school", "driving_school", "prep_school",
    "beauty", "hairdresser",
)
VERTICAL_SHOPS = (
    "clothes", "bakery", "florist", "furniture", "jewelry",
    "electronics", "optician", "travel_agency", "estate_agent",
    "stationery", "books", "musical_instrument", "sports",
)
