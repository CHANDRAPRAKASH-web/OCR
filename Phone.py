# phone cleaning / normalization (place this near top of recognition.py, after imports)
import re
try:
    import phonenumbers  # pip install phonenumbers
except Exception:
    phonenumbers = None

def clean_phone(raw: str, region: str = 'US'):
    """Normalize and validate phone numbers.

    - Tries phonenumbers.parse + is_valid_number and returns INTERNATIONAL format.
    - Falls back to digits-only string if >=7 digits.
    - Returns None if nothing usable found.
    """
    if not raw:
        return None
    # quick sanitize keep + and digits
    s = re.sub(r'[^0-9+]', '', str(raw))
    if not s:
        return None

    # prefer using python-phonenumbers if available
    if phonenumbers is not None:
        try:
            if s.startswith('+'):
                pn = phonenumbers.parse(s, None)
            else:
                pn = phonenumbers.parse(s, region)
            if phonenumbers.is_valid_number(pn):
                return phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        except Exception:
            # ignore and fallback to digits-only below
            pass

    # fallback: digits-only if reasonably long
    digits = re.sub(r'\D', '', s)
    if len(digits) >= 7:
        return digits
    return None
