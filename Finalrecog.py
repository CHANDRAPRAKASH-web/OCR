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
import unicodedata

# small debug toggle
DEBUG = False

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
    cur_right = None
    for w in word_data_sorted:
        left = int(w.get('left',0))
        top = int(w.get('top',0))
        width = int(w.get('width',0))
        text = (w.get('text','') or '').strip()
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
        cur_right = left + width
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
        text = (w.get('text','') or '').strip()
        if text == '':
            continue
        if prev_right is None:
            out.append(text)
        else:
            gap = left - prev_right
            # use a space when gap is small or large - tesseract often misses spaces
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
    # numbers + letters together often indicate addresses
    if re.search(r'\d', s) and any(ch.isalpha() for ch in s):
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
    # raw can be a dict from tesseract image_to_data
    confs = []
    if isinstance(raw, dict):
        c = raw.get('conf') or raw.get('confidence') or raw.get('confidences') or raw.get('level_confidence')
        if isinstance(c, (list, tuple)):
            confs = c
    vals = []
    for ci in confs:
        try:
            fv = float(ci)
            if fv >= 0:
                vals.append(fv)
        except Exception:
            continue
    return float(mean(vals)) if vals else 0.0

class Recognize:
    def __init__(self):
        pass

    def extract(self, image_bytes, lang="eng"):
        """
        Primary extractor: runs tesseract -> builds cleaned structured_lines -> extracts fields.
        Returns dict with expected keys (name, designation, company, email, mobile, website, address, lines, confidence, language_detected, osd_rotation)
        """
        # OSD
        try:
            osd_rotation = driver.get_osd_rotation(image_bytes)
        except Exception:
            osd_rotation = 0

        # preprocess and run tesseract once
        pre = preprocess_image(image_bytes)
        try:
            data = run_tesseract_data(pre, lang=lang)
        except Exception:
            # fallback via driver if run_tesseract_data not present
            try:
                data = driver.run_tesseract_data(pre, lang=lang)
            except Exception:
                data = {}

        # ensure data is a dict with lists
        if not isinstance(data, dict):
            data = {}

        # tolerant access to lists
        texts = data.get("text") or []
        lefts = data.get("left") or []
        tops = data.get("top") or []
        widths = data.get("width") or []
        heights = data.get("height") or []
        confs = data.get("conf") or data.get("confidence") or []

        # DEBUG dump
        if DEBUG:
            try:
                print("DEBUG: tesseract keys:", list(data.keys()))
                print("DEBUG: len(texts)=", len(texts), "len(confs)=", len(confs))
            except Exception:
                pass

        # Build structured_lines from per-word TSV if word-level positions exist,
        # otherwise fallback to text lines returned by tesseract.
        structured_lines = []

        # If we have word coordinates, build word_data and group lines
        if texts and (lefts or tops or widths):
            # Build list of per-word dictionaries (use indices up to length of texts)
            word_data = []
            n = len(texts)
            for i in range(n):
                t = texts[i] if i < len(texts) else ""
                l = lefts[i] if i < len(lefts) else 0
                tp = tops[i] if i < len(tops) else 0
                w = widths[i] if i < len(widths) else 0
                h = heights[i] if i < len(heights) else 0
                word_data.append({
                    "text": robust_str(t),
                    "left": int(l) if _is_int_like(l) else 0,
                    "top": int(tp) if _is_int_like(tp) else 0,
                    "width": int(w) if _is_int_like(w) else 0,
                    "height": int(h) if _is_int_like(h) else 0
                })

            # Group into line strings
            lines_grouped = group_words_by_line_using_tsv(word_data, gap_tol_px=12)
            # Build structured_lines using grouped lines (no per-line confidence available here)
            for idx, line_text in enumerate(lines_grouped):
                structured_lines.append({"idx": idx, "text": robust_str(line_text).strip(), "conf": 0.0})
        else:
            # fallback: tesseract gave whole-lines in texts
            for i, t in enumerate(texts):
                structured_lines.append({"idx": i, "text": robust_str(t).strip(), "conf": float(confs[i]) if i < len(confs) and _is_float_like(confs[i]) else 0.0})

        # ------- Clean & normalize each structured line -------
        _camel_split_re = re.compile(r'([a-z])([A-Z])')
        _leading_nan_re = re.compile(r'^(?:nan|none|null|nan,|,)+\s*', re.I)
        _nonprint_re = re.compile(r'[\x00-\x1f\x7f]+')

        for ln in structured_lines:
            s = ln.get("text", "") or ""
            try:
                s = unicodedata.normalize("NFKC", s)
            except Exception:
                pass
            s = _nonprint_re.sub(" ", s)
            s = s.strip()

            # remove literal 'nan' / 'none' / 'null' prefixes or repeated punctuation that start the string
            s = _leading_nan_re.sub("", s).strip()

            # if the text has a stray single leading char before an email (like "yhello@..") remove it
            if s and EMAIL_RE.search(s):
                # remove non-alnum characters at start
                s = re.sub(r'^[^A-Za-z0-9@+]+', '', s)
                # if starts with a single letter followed
