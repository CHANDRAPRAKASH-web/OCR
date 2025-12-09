import re
import math

def is_missing(x):
    if x is None: 
        return True
    s = str(x).strip()
    if s == "" or s.lower() in ("none", "nan", "n/a", "-"):
        return True
    return False

def clean_space_artifacts(s):
    if s is None:
        return None
    s = str(s)
    s = s.replace('\r',' ').replace('\n',' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return s if s else None

def split_camel_words(s):
    # insert space between lower+upper e.g. "OliviaWilson" -> "Olivia Wilson"
    if not s: 
        return s
    return re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)

def fix_ocr_common_confusions(s):
    if not s: 
        return s
    s = s.replace('0','0')  # placeholder if you want specific fixes
    s = s.replace('l','l')   # keep as placeholder
    # add very specific replacements if you repeatedly see same errors:
    s = s.replace('Wfy', 'Wy')   # example: "Wfy" -> "Wy"
    s = s.replace('fon', 'fon')   # no-op placeholder
    return s

def normalize_phone(s):
    if not s: 
        return None
    s = str(s)
    # remove everything except + and digits
    s2 = re.sub(r'[^0-9+]', '', s)
    # remove leading + if it's repeated
    if s2.startswith('+'):
        # keep single leading + then digits
        s2 = '+' + re.sub(r'[^0-9]', '', s2[1:])
    # now collapse to digits only for formatting
    digits = re.sub(r'[^0-9]', '', s2)
    if len(digits) == 0:
        return None
    # heuristics: if 10 digits -> local format, if longer keep as-is with + if present
    if len(digits) == 10:
        return f"+{digits}"  # unify as +country-10digits (user can change)
    if len(digits) > 10 and s2.startswith('+'):
        return f"+{digits}"
    if len(digits) >= 7:
        return digits
    return digits

def choose_address(lines):
    # lines: list of strings (grouped lines of text in reading order)
    # Heuristics: take last 2-3 non-empty lines that contain digits or common address tokens
    if not lines:
        return None
    addr_lines = []
    # reverse scan to accumulate address-like fragments
    for ln in reversed(lines):
        if is_missing(ln):
            continue
        L = ln.lower()
        if re.search(r'\d', L) or any(tok in L for tok in ('st', 'street', 'rd', 'road', 'ave', 'city', 'state', 'zip', 'pobox', 'po box')):
            addr_lines.insert(0, clean_space_artifacts(ln))
            # stop when we have 2 or 3 fragments
            if len(addr_lines) >= 3:
                break
    if not addr_lines:
        # fallback: return last non-empty 1-2 lines
        for ln in reversed(lines):
            ln_clean = clean_space_artifacts(ln)
            if ln_clean:
                addr_lines.insert(0, ln_clean)
                if len(addr_lines) >= 2:
                    break
    return ', '.join(addr_lines) if addr_lines else None

def average_confidence(confs):
    # confs could contain numeric strings or numbers; ignore None/NaN
    vals = []
    for c in confs:
        try:
            v = float(c)
            if math.isfinite(v):
                vals.append(v)
        except Exception:
            continue
    if not vals:
        return 0.0
    return sum(vals)/len(vals)
