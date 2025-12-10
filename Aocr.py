import re
import math
from statistics import mean
from typing import List, Dict, Any
import numpy as np
import phonenumbers

# try to import project drivers/helpers if present
try:
    from . import tesseract_driver as driver
    from ocr.preprocess import preprocess_image
    from ocr.tesseract_driver import run_tesseract_data, get_osd_rotation
except Exception:
    # fallback stubs (so file imports without crashing in environments missing modules)
    driver = None
    def preprocess_image(x): return x
    def run_tesseract_data(x, lang="eng"):
        # return empty structure if driver missing
        return {"text": [], "conf": [], "raw": {}}
    def get_osd_rotation(x): return 0

try:
    from ocr.heuristics import pick_name_company
except Exception:
    def pick_name_company(lines, confs):
        return (None, None)

# small helpers
def robust_str(x):
    if x is None:
        return ''
    s = str(x).strip()
    if s.lower() in ('nan', 'none', 'null'):
        return ''
    return s

PHONE_RE = re.compile(r'(\+?\d[\d\-\s().]{6,}\d)')
EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
WEBSITE_RE = re.compile(r'(https?://\S+|www\.\S+)')
ZIP_RE = re.compile(r'\b\d{5}(?:-\d{4})?\b')
STREET_KEYWORDS = [
    'street', 'st', 'road', 'rd', 'avenue', 'ave', 'lane', 'ln', 'drive', 'dr', 'boulevard',
    'blvd', 'way', 'square', 'sq', 'court', 'ct', 'plaza', 'plz', 'highway', 'hwy'
]
DESIGNATION_KEYWORDS = [
    'manager','director','engineer','developer','founder','ceo','co-founder','consultant','agent','sales',
    'representative','analyst','architect','officer','head','lead'
]

def _avg_confidence_from_raw(raw):
    confs = []
    if isinstance(raw, dict):
        maybe = raw.get('conf') or raw.get('confidence') or []
        if isinstance(maybe, (list, tuple)):
            confs = maybe
    vals = []
    for c in confs:
        try:
            ci = float(c)
            if ci >= 0:
                vals.append(ci)
        except Exception:
            continue
    return float(mean(vals)) if vals else 0.0

def _clean_phone_digits(raw: str):
    if not raw:
        return None
    s = re.sub(r'[^0-9+]', '', raw)
    if not s:
        return None
    try:
        if not s.startswith('+'):
            pn = phonenumbers.parse(s, "US")
        else:
            pn = phonenumbers.parse(s, None)
        if phonenumbers.is_valid_number(pn):
            return phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
    except Exception:
        pass
    # fallback digits
    digits = re.sub(r'\D', '', raw)
    return digits if len(digits) >= 7 else None

def looks_like_address(s: str) -> bool:
    if not s or len(s) < 4:
        return False
    low = s.lower()
    if any(k in low for k in STREET_KEYWORDS):
        return True
    if ZIP_RE.search(s):
        return True
    if re.search(r'\d', s) and re.search(r'[A-Za-z]', s):
        return True
    return False

class Recognize:
    def __init__(self):
        pass

    def extract(self, image_bytes, lang="eng"):
        """Return final extracted dict (name, email, mobile, website, etc.)"""
        # rotation attempt
        try:
            osd_rotation = get_osd_rotation(image_bytes) if callable(get_osd_rotation) else 0
        except Exception:
            osd_rotation = 0

        pre = preprocess_image(image_bytes) if callable(preprocess_image) else image_bytes

        # try to run tesseract - driver.run_tesseract_data if available, else fallback to run_tesseract_data
        try:
            if driver is not None and hasattr(driver, "run_tesseract_data"):
                data = driver.run_tesseract_data(pre, lang=lang)
            else:
                data = run_tesseract_data(pre, lang=lang)
        except Exception:
            data = {"text": [], "conf": [], "raw": {}}

        # normalize data
        if not isinstance(data, dict):
            data = {"text": [], "conf": [], "raw": {}}

        # tesseract may place lines in top-level "text" or inside data["raw"]["text"]
        lines_src = data.get("text") or []
        raw = data.get("raw") or {}
        # if raw contains nested text, use it as fallback
        if (not lines_src) and isinstance(raw, dict) and raw.get("text"):
            lines_src = raw.get("text", [])

        conf_list = []
        # raw conf often available as raw['conf'] (list); fallback to data.get('conf')
        if isinstance(raw, dict):
            conf_list = raw.get("conf") or []
        if not conf_list:
            conf_list = data.get("conf") or []

        # build structured_lines safely
        structured_lines = []
        for i, txt in enumerate(lines_src):
            # ensure string
            if txt is None:
                txt = ""
            if isinstance(txt, bytes):
                try:
                    txt = txt.decode("utf-8", "ignore")
                except Exception:
                    txt = str(txt)
            txt = robust_str(txt)

            # try to unescape obvious literal escapes (like "\\n" showing in OCR)
            try:
                txt = txt.encode("utf-8").decode("unicode_escape")
            except Exception:
                pass

            # remove leading junk tokens
            txt = re.sub(r'^(?:nan|none|null|nil|n/a)[\s,:-]*', '', txt, flags=re.I)

            # remove weird repeated backslashes sequences often produced by escape artifacts
            txt = re.sub(r'\\{2,}', r'\\', txt)
            txt = re.sub(r'\s{2,}', ' ', txt).strip()

            # remove leading non-alnum except keep + and @ for phones/emails
            txt = re.sub(r'^[^A-Za-z0-9+@]+', '', txt)

            try:
                conf_val = float(conf_list[i]) if i < len(conf_list) else 0.0
            except Exception:
                conf_val = 0.0

            structured_lines.append({
                "idx": i,
                "text": txt,
                "conf": conf_val
            })

        # compute contact candidates
        found_email = None
        found_phone = None
        found_website = None

        for ln in structured_lines:
            s = ln.get("text", "") or ""
            if not found_email:
                m = EMAIL_RE.search(s)
                if m:
                    found_email = m.group(0)
            if not found_phone:
                m = PHONE_RE.search(s)
                if m:
                    found_phone = _clean_phone_digits(m.group(0))
            if not found_website:
                m = WEBSITE_RE.search(s)
                if m:
                    found_website = m.group(0)

        # address extraction: pick an anchor that looks like an address (lowest such line)
        address_lines = []
        address_hints = [ln for ln in structured_lines if looks_like_address(ln.get("text",""))]
        if address_hints:
            anchor = max(address_hints, key=lambda x: x.get("idx", 0))
            i = int(anchor.get("idx", 0))
            # expand upward (max 6 lines) and downward (max 4)
            # upward
            j = i
            added = 0
            while j >= 0 and added < 6:
                ln = structured_lines[j]
                txt = (ln.get("text") or "").strip()
                if txt == "":
                    j -= 1
                    continue
                if EMAIL_RE.search(txt) or PHONE_RE.search(txt) or WEBSITE_RE.search(txt):
                    break
                address_lines.insert(0, txt)
                added += 1
                j -= 1
            # downward
            k = i + 1
            added_down = 0
            while k < len(structured_lines) and added_down < 4:
                ln2 = structured_lines[k]
                t2 = (ln2.get("text") or "").strip()
                if t2 == "":
                    k += 1
                    continue
                if EMAIL_RE.search(t2) or PHONE_RE.search(t2) or WEBSITE_RE.search(t2):
                    break
                address_lines.append(t2)
                added_down += 1
                k += 1

        # designation and name heuristics: prefer pick_name_company if available
        name_candidate = None
        company_candidate = None
        designation = None
        try:
            # use pick_name_company if it returns (name, company)
            nm, cmp = pick_name_company([ln.get("text","") for ln in structured_lines],
                                        [ln.get("conf",0.0) for ln in structured_lines])
            if nm:
                name_candidate = nm
            if cmp:
                company_candidate = cmp
        except Exception:
            pass

        # fallback simple heuristics if pick_name_company didn't produce results
        if not name_candidate:
            # possible name: not contact, not address, short (1-3 words), TitleCase token present
            candidates = []
            for ln in structured_lines[:10]:
                s = ln.get("text","")
                if not s:
                    continue
                if EMAIL_RE.search(s) or PHONE_RE.search(s) or WEBSITE_RE.search(s) or looks_like_address(s):
                    continue
                words = [w.strip(",.()") for w in s.split() if w.strip(",.()")]
                if 1 <= len(words) <= 3:
                    if any(w and w[0].isupper() for w in words):
                        candidates.append(ln)
            if candidates:
                candidates.sort(key=lambda x: (-x.get("conf",0.0), x.get("idx",0)))
                name_candidate = candidates[0].get("text")

        if not designation:
            for ln in structured_lines:
                low = (ln.get("text") or "").lower()
                if any(k in low for k in DESIGNATION_KEYWORDS):
                    designation = ln.get("text")
                    break

        if not company_candidate:
            for ln in structured_lines[:10]:
                s = ln.get("text","")
                if not s:
                    continue
                if s == name_candidate or s == designation:
                    continue
                if EMAIL_RE.search(s) or PHONE_RE.search(s) or WEBSITE_RE.search(s) or looks_like_address(s):
                    continue
                company_candidate = s
                break
