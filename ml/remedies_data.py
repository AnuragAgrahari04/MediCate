"""
Multilingual Home Remedies & Immediate First-Aid registry for MediCate.
Covers all 41 disease classes in English and Hindi (Devanagari).
"""

from ml.remedies_en import REMEDIES_EN
from ml.remedies_hi import REMEDIES_HI

SUPPORTED_REMEDY_LANGUAGES = [
    {'code': 'en', 'label': 'English', 'short': 'EN'},
    {'code': 'hi', 'label': 'हिंदी', 'short': 'हिं'},
]

_LANG_MAP = {
    'en': REMEDIES_EN,
    'hi': REMEDIES_HI,
}

# Normalize UI/dataset variants to the canonical keys in REMEDIES_*
_DISEASE_ALIASES = {
    'osteoarthritis': 'Osteoarthristis',
    'osteoarthristis': 'Osteoarthristis',
    '(vertigo) paroymsal positional vertigo': '(vertigo) Paroymsal  Positional Vertigo',
    '(vertigo) paroymsal  positional vertigo': '(vertigo) Paroymsal  Positional Vertigo',
    'peptic ulcer disease': 'Peptic ulcer diseae',
    'peptic ulcer diseae': 'Peptic ulcer diseae',
    'hepatitis a': 'hepatitis A',
    'dimorphic hemmorhoids(piles)': 'Dimorphic hemmorhoids(piles)',
}

UI_STRINGS = {
    'en': {
        'card_title': 'Home Remedies & Immediate Care',
        'subtitle': 'Practical steps you can take right now while preparing to consult a doctor',
        'avoid_title': 'What to Avoid',
        'red_flag_title': 'Seek Medical Care Immediately If',
        'tiers': {
            'home': 'Home Care Friendly',
            'supportive': 'Supportive Care · See Doctor Soon',
            'emergency': 'Medical Emergency · Act Fast',
        },
    },
    'hi': {
        'card_title': 'घरेलू उपाय और प्राथमिक देखभाल',
        'subtitle': 'डॉक्टर से मिलने तक राहत और सुरक्षा के लिए तुरंत अपनाने योग्य कदम',
        'avoid_title': 'क्या न करें (सावधानियां)',
        'red_flag_title': 'तुरंत डॉक्टर / इमरजेंसी में जाएं यदि',
        'tiers': {
            'home': 'घरेलू देखभाल योग्य',
            'supportive': 'सहायक देखभाल · डॉक्टर को दिखाएं',
            'emergency': 'गंभीर आपातकाल · तुरंत मदद लें',
        },
    },
}


def normalize_disease_key(disease_name: str) -> str:
    """Resolve minor spelling/spacing differences to the canonical disease key."""
    if not disease_name:
        return ''
    cleaned = ' '.join(disease_name.strip().split())
    lower = cleaned.lower()
    if lower in _DISEASE_ALIASES:
        return _DISEASE_ALIASES[lower]
    for key in REMEDIES_EN:
        if key.lower() == lower or ' '.join(key.lower().split()) == lower:
            return key
    return disease_name.strip()


def get_disease_remedies(disease_name: str, lang: str = 'en') -> dict:
    """
    Return localized home remedies / first-aid payload for a predicted disease.
    Always falls back cleanly to English if a language code or entry is missing.
    """
    lang_code = lang if lang in _LANG_MAP else 'en'
    canonical = normalize_disease_key(disease_name)

    lang_book = _LANG_MAP[lang_code]
    entry = lang_book.get(canonical) or REMEDIES_EN.get(canonical)
    ui = UI_STRINGS.get(lang_code, UI_STRINGS['en'])

    if not entry:
        return {
            'disease': disease_name,
            'lang': lang_code,
            'tier': 'supportive',
            'tier_label': ui['tiers']['supportive'],
            'ui': ui,
            'intro': 'Stay hydrated, rest well, and consult a qualified doctor for personalized guidance.',
            'remedies': [
                {'icon': '💧', 'title': 'Stay Hydrated', 'detail': 'Drink clean water or ORS to support recovery.'},
                {'icon': '🛌', 'title': 'Rest & Monitor', 'detail': 'Track fever or new symptoms until your appointment.'},
            ],
            'avoid': ['Self-medicating strong prescription drugs'],
            'seek_doctor_when': 'Consult a doctor promptly if symptoms worsen or new warning signs appear.',
            'languages': SUPPORTED_REMEDY_LANGUAGES,
        }

    tier = entry['tier']
    return {
        'disease': disease_name,
        'canonical_disease': canonical,
        'lang': lang_code,
        'tier': tier,
        'tier_label': ui['tiers'].get(tier, ui['tiers']['supportive']),
        'ui': ui,
        'intro': entry['intro'],
        'remedies': entry['remedies'],
        'avoid': entry['avoid'],
        'seek_doctor_when': entry['seek_doctor_when'],
        'languages': SUPPORTED_REMEDY_LANGUAGES,
    }
