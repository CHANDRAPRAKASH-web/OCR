import re
from . import tesseract_driver as driver
from statistics import mean
from ocr.preprocess import preprocess_image
from ocr.tesseract_driver import run_tesseract_data, get_osd_rotation
from ocr.heuristics import pick_name_company
import math
from typing import List, Dict, Any
import phonenumbers   # pip install phonenumbers
import numpy as np

def sanitize(obj: Any):
    """Return an object safe to JSON encode: replace NaN/inf and np types."""
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, (np.floating, np.integer)):
        # convert numpy types to python types
        python_val = obj.item()
        return sanitize(python_val)
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    # default primitives (str, int, bool)
    return obj

# ---------- regroup words from tesseract word-level TSV ----------
def group_words_by_line_using_tsv(word_data: List[Dict[str,Any]], gap_tol_px:int=15):
    """
    Recreate lines from per-word tsv output.
    word_data: list of dicts; each dict should have keys: left, top, width, height, text
    gap_tol_px: if horizontal gap between run end and next word start greater than this -> insert space
    returns list of lines (strings) in reading order.
    """
    # sort by top, then left
    word_data_sorted = sorted(word_data, key=lambda w: (int(w.get('top',0)), int(w.get('left',0))))
    lines = []
    cur_line = []
    # compute mean height to help grouping
    heights = [int(w.get('height', 0)) for w in word_data_sorted if w.get('height',0)]
    mean_h = int(np.mean(heights)) if heights else 0

    # cluster by vertical proximity
    cur_top = None
    for w in word_data_sorted:
        left = int(w.get('left',0))
        top = int(w.get('top',0))
        width = int(w.get('width',0))
        text = w.get('text','').strip()
        if not text:
            continue
        if cur_top is None:
            cur_top = top
            cur_line = [w]
            cur_right = left + width
            continue
        # if top is within half mean height -> same line
        if abs(top - cur_top) <= max(8, mean_h//2):
            cur_line.append(w)
            cur_right = left + width
            continue
        # else end current line
        # assemble current line string by sorting left and inserting spaces based on gap
        lines.append(_assemble_line_from_words(cur_line, gap_tol_px))
        cur_line = [w]
        cur_top = top
    if cur_line:
        lines.append(_assemble_line_from_words(cur_line, gap_tol_px))
    return lines

def _assemble_line_from_words(words: List[Dict[str,Any]], gap_tol_px:int=15):
    # sort by left coordinate
    words_sorted = sorted(words, key=lambda x: int(x.get('left',0)))
    out = []
    prev_right = None
    for w in words_sorted:
        left = int(w.get('left',0))
        width = int(w.get('width',0))
        text = w.get('text','').strip()
        if text == '':
            continue
        if prev_right is None:
            out.append(text)
        else:
            gap = left - prev_right
            if gap > gap_tol_px:
                out.append(' ' + text)   # big gap -> separate word with a space
            else:
                # small gap -> just add a space too (better than concatenation)
                out.append(' ' + text)
        prev_right = left + width
    # join preserving inserted spaces
    return ''.join(out).strip()

# ---------- phone cleaning ----------
def clean_phone(raw: str, region='US'):
    if not raw:
        return None
    s = re.sub(r'[^0-9+]', '', raw)
    if len(s) == 0:
        return None
    try:
        if not s.startswith('+'):
            # try parse with default region
            pn = phonenumbers.parse(s, region)
        else:
            pn = phonenumbers.parse(s, None)
        if phonenumbers.is_valid_number(pn):
            return phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        # fallback: return digits-only if length >= 7
        digits = re.sub(r'\D', '', raw)
        if len(digits) >= 7:
            return digits
        return None
    except Exception:
        digits = re.sub(r'\D', '', raw)
        return digits if len(digits) >= 7 else None

# ---------- address heuristics ----------
_ADDRESS_RE = re.compile(r'\b(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Lane|Ln|Way|Suite|Ste|Apt|Floor|Fl)\b', re.I)
def looks_like_address(s: str):
    if not s or len(s) < 4:
        return False
    if _ADDRESS_RE.search(s):
        return True
    # zip-like pattern
    if re.search(r'\b\d{5}(?:-\d{4})?\b', s):
        return True
    return False

def normalize_address(multi_line_address: str):
    # collapse many whitespaces, ensure commas between components if missing
    parts = [p.strip() for p in re.split(r'\n|,', multi_line_address) if p and p.strip()]
    # join with commas, but try to keep street+apt together
    return ', '.join(parts)

# ---------- small helper to fix any 'nan' string if present  ----------
def robust_str(x):
    """Return a human string: convert None -> '' and remove literal 'nan' strings."""
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
    def __init__(self):                       # <<< FIX: constructor name corrected
        pass

    def extract(self, image_bytes, lang="eng"):
        try:
            osd_rotation = driver.get_osd_rotation(image_bytes)
        except Exception:
            osd_rotation = 0
        
        pre= preprocess_image(image_bytes)
        # --- DEBUG CHECK: ensure tesseract output is correct ---
        try:
            if hasattr(driver, "run_tesseract_data"):
                data = driver.run_tesseract_data(pre, lang=lang)
            else:
                data = run_tesseract_data(pre, lang=lang)

            print("DEBUG: run_tesseract_data type:", type(data))
            if isinstance(data, dict):
                print("DEBUG: keys:", list(data.keys()))
                for k in ("text", "left", "top", "width", "height", "conf", "raw"):
                    if k in data:
                        v = data[k]
                        if isinstance(v, (list, tuple)):
                            print(f"DEBUG: len({k}) =", len(v))
                        else:
                            print(f"DEBUG: {k} type =", type(v))
            else:
                print("DEBUG: NOT A DICT:", data)

        except Exception as e:
            print("ERROR in tesseract:", repr(e))
            data = {}
        # --- END DEBUG ---


        data= run_tesseract_data(pre)
        # ========== DEBUG: dump tesseract outputs (temporary) ==========
        try:
            print("DEBUG: run_tesseract_data type:", type(data))
            print("DEBUG: keys:", list(data.keys()))
            txt_list = data.get("text", [])
            conf_list = data.get("conf", [])
            raw = data.get("raw", {})
            print("DEBUG: len(text) =", len(txt_list))
            print("DEBUG: len(conf) =", len(conf_list))
            # print first 12 text/conf items for inspection
            for i, t in enumerate(txt_list[:12]):
                c = conf_list[i] if i < len(conf_list) else None
                print(f"DEBUG: text[{i!s}]: {repr(t)}  conf[{i!s}]: {repr(c)}")
            # if there is a 'raw' or nested 'text' in raw, print keys
            if isinstance(raw, dict):
                print("DEBUG: raw keys:", list(raw.keys()))
                if "text" in raw:
                    print("DEBUG: first 6 raw['text']:", [repr(x) for x in raw.get("text", [])[:6]])
        except Exception as _dbg_e:
            print("DEBUG: error dumping tesseract data:", _dbg_e)
        # ==============================================================
        lines= data["text"]
        confs= data["conf"]

        name, company= pick_name_company(lines, confs)

        data = driver.run_tesseract_data(image_bytes, lang=lang)
        # data expected structure:
        # data["text"] -> list of lines (strings)
        # data["raw"]  -> raw tesseract image_to_data dict (with 'conf' etc)
        lines_raw = data.get("text", []) or []
        raw = data.get("raw", {}) or {}

        # build lines with confidences (if available)
        conf_list = raw.get("conf", [])
        structured_lines = []
        for i, txt in enumerate(lines_raw):
            c = None
            try:
                c = float(conf_list[i]) if i < len(conf_list) else None
            except Exception:
                c = None
            # clean the raw OCR text into a safe, human string
        clean_txt = robust_str(txt).strip()

        # remove literal 'nan ' prefix or other literal tokens at start
        if clean_txt.lower().startswith('nan '):
            clean_txt = clean_txt[4:].strip()

        # if the whole token is a literal null-like string, make it empty
        if clean_txt.lower() in ('nan', 'none', 'null'):
            clean_txt = ''

        # normalize multiple internal whitespace and remove stray repeated punctuation
        clean_txt = re.sub(r'\s+', ' ', clean_txt).strip()

        structured_lines.append({
           "idx": i,
           "text": clean_txt,
            "conf": c or 0.0
        })

        # ----- CLEAN & NORMALIZE TEXT LINES (small fixes, keep original vars) -----
        import unicodedata
        _camel_split_re = re.compile(r'([a-z])([A-Z])')   # to separate "OliviaWilson" -> "Olivia Wilson"
        _leading_nan_re = re.compile(r'^(?:nan|none|null|nan,|\-)+\s*', re.I)  # remove leading nan/null junk
        _nonprint_re = re.compile(r'[\x00-\x1f\x7f]+')  # control chars

        for ln in structured_lines:
            txt = ln.get("text", "") or ""
            # normalize unicode and remove control chars
            try:
                txt = unicodedata.normalize("NFKC", txt)
            except Exception:
                pass
            txt = _nonprint_re.sub(" ", txt)

            # remove repeating 'nan' or other literal tokens at start (OCR artifact)
            txt = _leading_nan_re.sub("", txt).strip()

            # if text begins with stray non-alnum characters (like stray 'y' or punctuation),
            # but contains an email later, remove leading single non-alpha char only when it
            # is immediately before an alpha (covers "yhello@..." -> "hello@...")
            if txt and not txt[0].isalnum():
                # keep single leading '+' (phone international)
                if not txt.startswith('+'):
                    if EMAIL_RE.search(txt):
                        # remove only leading non-alnum chars
                        txt = re.sub(r'^[^A-Za-z0-9@+]+', '', txt)
                    else:
                        txt = re.sub(r'^[^A-Za-z0-9+]+', '', txt)

            # split camel-case TitleCase merges: "OliviaWilson" -> "Olivia Wilson"
            # but only if the token looks like a name (no digits, has uppercase transitions)
            if txt and re.search(r'[A-Z][a-z]+[A-Z][a-z]+', txt):
                txt = _camel_split_re.sub(r'\1 \2', txt)

            # collapse multi-space and trim
            txt = re.sub(r'\s{2,}', ' ', txt).strip()

            # replace solitary repeated punctuation/comma sequences that break tokens
            txt = re.sub(r'[,;:\-]{2,}', ',', txt)

            # final fallback: convert literal "nan" words to empty
            if txt.lower() in ("nan", "none", "null"):
                txt = ""

            # ensure confidence is a number (0 if missing)
            try:
                ln["conf"] = float(ln.get("conf") or 0.0)
            except Exception:
                ln["conf"] = 0.0

            ln["text"] = txt
            ln["clean_words"] = [w.strip(".,;:!()[]") for w in txt.split() if w.strip(".,;:!()[]")]

            # update ln text to cleaned result
            ln["text"] = s
            is_email= lambda s: EMAIL_RE.search(s) is not None
            is_phone= lambda s: PHONE_RE.search(s) is not None
            is_website= lambda s: WEBSITE_RE.search(s) is not None
            looks_like_address= looks_like_address

            # now compute flags / clean_words using cleaned text
            ln["is_contact"] = bool(is_email(s) or is_phone(s) or is_website(s))
            ln["is_address_hint"] = bool(looks_like_address(s))
            ln["clean_words"] = [w.strip(".,") for w in s.split() if w.strip(".,")]

        # extract contact info first
        found_email = None
        found_phone = None
        found_website = None
        for ln in structured_lines:
            s = ln["text"] or ""
            if not found_email and is_email(s):
                m= EMAIL_RE.search(s)
                if m:
                    found_email = m.group(0)
            if not found_phone and is_phone(s):
                found_phone = _clean_phone(PHONE_RE.search(s).group(0))
            if not found_website and is_website(s):
                found_website = WEBSITE_RE.search(s).group(0)

        # find contiguous address block starting from any address hint near bottom
        # find contiguous address block starting from any address hint near bottom
        address_lines = []
        if structured_lines:
            # find lines that look like address hints
            address_hints = [ln for ln in structured_lines if ln.get("is_address_hint")]
            if address_hints:
                # pick the lowest hint (highest idx)
                anchor = max(address_hints, key=lambda x: x.get("idx", 0))
                i = anchor.get("idx", None)
                # guard: ensure i is a valid index in structured_lines
                if i is None:
                    i = None
                else:
                    try:
                        i = int(i)
                    except Exception:
                        i = None

                if i is not None and 0 <= i < len(structured_lines):
                    # expand upward from anchor while staying in bounds
                    j = i
                    added = 0
                    while j >= 0 and added < 6:   # limit safety: do not loop forever; max 6 lines
                        ln = structured_lines[j]
                        # stop expansion if line is clearly contact info (email/phone/website)
                        if ln.get("is_contact"):
                            break
                        text = (ln.get("text") or "").strip()
                        # skip empty or nonsense lines, but allow a single short gap
                        if text == "":
                            j -= 1
                            continue
                        # insert at front (we're moving upward)
                        address_lines.insert(0, text)
                        added += 1
                        j -= 1

                    # also try to expand downward a little to capture trailing address lines
                    k = i + 1
                    added_down = 0
                    while k < len(structured_lines) and added_down < 4:
                        ln2 = structured_lines[k]
                        if ln2.get("is_contact"):
                            break
                        t2 = (ln2.get("text") or "").strip()
                        if t2 == "":
                            k += 1
                            continue
                        address_lines.append(t2)
                        added_down += 1
                        k += 1
                else:
                    # anchor idx invalid — fallback: try to pick the last few lines that look like addresses
                    candidates = [ln.get("text","").strip() for ln in structured_lines if ln.get("is_address_hint")]
                    # take last up to 3 hints as fallback
                    if candidates:
                        address_lines = candidates[-3:]

        # find designation (anywhere)
        designation = None
        for ln in structured_lines:
            low = ln["text"].lower()
            if any(k in low for k in DESIGNATION_KEYWORDS):
                designation = ln["text"]
                break

        # find name candidate
        name_candidate = None
        # heuristics: short (2-3 words), TitleCase words (start with uppercase), no digits, not contact, not address
        possible = []
        for ln in structured_lines:
            s = ln["text"]
            if not s or ln["is_contact"] or ln["is_address_hint"]:
                continue
            words = ln["clean_words"]
            if 2 <= len(words) <= 3:
                if any(ch.isdigit() for ch in s):
                    continue
                # check Title-case ratio
                tc = sum(1 for w in words if w and w[0].isupper())
                if tc >= 1:
                    possible.append(ln)
        # prefer highest confidence among possibles and earlier lines (top of card)
        if possible:
            possible.sort(key=lambda x: (-x["conf"], x["idx"]))
            name_candidate = possible[0]["text"]

        # company candidate: first non-contact/non-address line near the top if not name
        company_candidate = None
        for ln in structured_lines:
            s = ln["text"]
            if not s or ln["is_contact"] or ln["is_address_hint"]:
                continue
            if name_candidate and s == name_candidate:
                continue
            # Skip if likely designation
            if designation and s == designation:
                continue
            # choose a longer line >2 words as company
            if len(ln["clean_words"]) >= 1:
                company_candidate = s
                break

        final = {
            "language_detected": lang,
            "osd_rotation": osd_rotation,
            "name": name_candidate or "",
            "designation": designation or "",
            "company": company_candidate or "",
            "email": found_email or "",
            "mobile": found_phone or "",
            "website": found_website or "",
            "address": "\n".join(address_lines).strip(),
            "lines": [ln["text"] for ln in structured_lines if (ln.get("text") or "").strip()],
            "confidence": round(_avg_confidence_from_raw(raw), 2),
            
        }
        return final

    def recognize(self, image_bytes, lang="eng"):
        try:
            img = preprocess_image(image_bytes)   # keep whatever preprocessing you already have
        except Exception:
            img = image_bytes

        try:
            osd = get_osd_rotation(img)
        except Exception:
            osd = ""

        # run tesseract to get tsv-style dict (should include keys: text, left, top, width, height, conf)
        data = run_tesseract_data(img, lang=lang)

        # Build word list for TSV grouping
        word_data = []
        texts = data.get("text", [])
        lefts = data.get("left", [])
        tops = data.get("top", [])
        widths = data.get("width", [])
        heights = data.get("height", [])

        for i, t in enumerate(texts):
            if not t:
                continue
            try:
                left = int(lefts[i]) if i < len(lefts) else 0
                top = int(tops[i]) if i < len(tops) else 0
                width = int(widths[i]) if i < len(widths) else 0
                height = int(heights[i]) if i < len(heights) else 0
            except Exception:
                left = top = width = height = 0

            word_data.append({
                "text": str(t).strip(),
                "left": left,
                "top": top,
                "width": width,
                "height": height
            })

        # Group words into lines using the TSV based helper we added at top-level
        lines_grouped = group_words_by_line_using_tsv(word_data, gap_tol_px=12)

        # convert to the old form expected by your extraction logic, if necessary
        # If your existing extract_fields accepts list of lines as strings, map accordingly:
        lines_for_extract = lines_grouped

        # Now call your existing extract_fields (or the method that extracts name/phone/email)
        extracted = self.extract(image_bytes, lang=lang)   # <<< FIX: call the existing extract pipeline

        # Clean phone numbers
        mobile_raw = extracted.get('mobile')
        if isinstance(mobile_raw, list):
            extracted['mobile'] = [clean_phone(p) for p in mobile_raw if p]
        else:
            # single string -> normalize it
            extracted['mobile'] = clean_phone(mobile_raw) if mobile_raw else ""

        # Normalize address if you have a helper normalize_address, else simple join
        addr = extracted.get("address", '')
        if isinstance(addr, list):
            extracted['address'] = "\n".join([a for a in addr if a])
        else:
            extracted['address'] = addr or ""

        # Add OSD and other metadata
        extracted['osd'] = osd
        extracted['language_detected'] = lang

        # Final sanitize to ensure JSON serializability
        final = sanitize(extracted)

        return final
