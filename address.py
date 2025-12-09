# put this in recognition.py or utils.py and import where needed

import math
import re
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
