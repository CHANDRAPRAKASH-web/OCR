import re
from . import tesseract_driver as driver
from statistics import mean

PHONE_RE = re.compile(r'(\+?\d[\d\-\s().]{6,}\d)')
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
WEBSITE_RE = re.compile(r'(https?://\S+|www\.\S+)')
ZIP_RE = re.compile(r'\b\d{5}(?:-\d{4})?\b')
STREET_KEYWORDS = [
    'street', 'st', 'road', 'rd', 'avenue', 'ave', 'lane', 'ln', 'drive', 'dr', 'boulevard', 'blvd',
    'way','square','sq','court','ct','plaza','plz','highway','hwy'
]

DESIGNATION_KEYWORDS = [
    'manager','director','engineer','developer','founder','ceo','co-founder','consultant','agent','sales',
    'representative','analyst','architect','officer','head','lead'
]

def _clean_phone(s: str) -> str:
    s = re.sub(r'[^\d+]', '', s)
    # basic normalization
    return s

def _line_has_address_hint(line: str) -> bool:
    low = line.lower()
    if any(k in low for k in STREET_KEYWORDS):
        return True
    if ZIP_RE.search(line):
        return True
    if re.search(r'\b\d{1,4}\b', line) and any(ch.isalpha() for ch in line):
        # contains numbers and letters - likely an address line
        return True
    return False

def _avg_confidence_from_raw(raw):
    # raw is the tesseract image_to_data dict
    confs = raw.get('conf', []) if isinstance(raw, dict) else []
    vals = []
    for c in confs:
        try:
            ci = float(c)
            if ci >= 0:
                vals.append(ci)
        except Exception:
            continue
    return float(mean(vals)) if vals else 0.0

class Recognize:
    def _init_(self):
        pass

    def extract(self, image_bytes, lang="eng"):
        # get osd rotation if possible
        try:
            osd_rotation = driver.get_osd_rotation(image_bytes)
        except Exception:
            osd_rotation = 0

        data = driver.run_tesseract_data(image_bytes, lang=lang)
        lines = data.get("text", []) or []
        raw = data.get("raw", {}) or {}

        # simple heuristics:
        found_email = None
        found_phone = None
        found_website = None
        address_lines = []
        name_candidate = None
        company_candidate = None
        designation = None

        # 1) scan lines for email/phone/website
        for li in lines:
            if not li or not li.strip():
                continue
            s = li.strip()
            if not found_email:
                m = EMAIL_RE.search(s)
                if m:
                    found_email = m.group(0)
            if not found_phone:
                m = PHONE_RE.search(s)
                if m:
                    phone_raw = m.group(0)
                    found_phone = _clean_phone(phone_raw)
            if not found_website:
                m = WEBSITE_RE.search(s)
                if m:
                    found_website = m.group(0)
            if _line_has_address_hint(s):
                address_lines.append(s)

        # 2) name / company / designation heuristics
        # assume first non-empty line may be a name
        for idx, li in enumerate(lines):
            s = li.strip()
            if not s:
                continue
            # skip lines that are obvious emails/phones/websites/addresses
            if EMAIL_RE.search(s) or PHONE_RE.search(s) or WEBSITE_RE.search(s) or _line_has_address_hint(s):
                continue
            # if it's short-ish and has capitals, treat as name
            if 2 <= len(s.split()) <= 4 and any(c.isalpha() for c in s):
                name_candidate = s
                # next non-empty line could be company or designation
                # check next lines
                for j in range(idx+1, min(idx+4, len(lines))):
                    s2 = lines[j].strip()
                    if not s2:
                        continue
                    low = s2.lower()
                    if any(k in low for k in DESIGNATION_KEYWORDS):
                        designation = s2
                        continue
                    # else treat first following non-address non-contact line as company
                    if not EMAIL_RE.search(s2) and not PHONE_RE.search(s2) and not WEBSITE_RE.search(s2) and not _line_has_address_hint(s2):
                        company_candidate = s2
                        break
                break

        # fallback: if name not found, maybe first line is a company -> set company
        if not name_candidate and lines:
            for li in lines:
                s = li.strip()
                if s and not EMAIL_RE.search(s) and not PHONE_RE.search(s) and not WEBSITE_RE.search(s):
                    company_candidate = s
                    break

        # 3) build final structured result
        final = {
            "language_detected": lang,
            "osd_rotation": osd_rotation,
            "name": name_candidate or "",
            "designation": designation or "",
            "company": company_candidate or "",
            "email": found_email or "",
            "mobile": found_phone or "",
            "website": found_website or "",
            "address": "\n".join(address_lines) if address_lines else "",
            "lines": lines,
            "confidence": round(_avg_confidence_from_raw(raw), 2),
            "raw": raw
        }
        return final
