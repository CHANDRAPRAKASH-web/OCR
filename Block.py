# --- build safe final dictionary (avoid returning regex objects or module constants) ---
import re as _re

def _safe_scalar_str(v):
    """Return safe string for a single value (empty if None or non-scalar like compiled regex)."""
    if v is None:
        return ""
    # compiled regex -> don't expose internals
    try:
        if isinstance(v, _re.Pattern):
            return ""
    except Exception:
        pass
    # if it's already a string, normalize whitespace
    if isinstance(v, str):
        return re.sub(r'\s+', ' ', v).strip()
    # numbers/booleans -> string form
    if isinstance(v, (int, float, bool)):
        return str(v)
    # lists/tuples -> join into newline; convert elements to strings
    if isinstance(v, (list, tuple)):
        items = [str(x).strip() for x in v if x is not None and str(x).strip()]
        return "\n".join(items)
    # fallback to str()
    try:
        s = str(v)
        return re.sub(r'\s+', ' ', s).strip()
    except Exception:
        return ""

# If some variable accidentally equals the module-level keyword list, don't expose it
if designation == DESIGNATION_KEYWORDS:
    designation_out = ""
else:
    designation_out = _safe_scalar_str(designation)

if isinstance(found_email, _re.Pattern):
    found_email = None
if isinstance(found_website, _re.Pattern):
    found_website = None

# lines: keep as list of non-empty cleaned strings
out_lines = []
for ln in structured_lines:
    t = ln.get("text", "") or ""
    t = t.strip()
    if t:
        out_lines.append(t)

# confidence: compute safely (raw may be missing)
try:
    conf_val = round(_avg_confidence_from_raw(raw), 2) if isinstance(raw, dict) else 0.0
except Exception:
    conf_val = 0.0

final = {
    "language_detected": lang,
    "osd_rotation": int(osd_rotation) if isinstance(osd_rotation, (int, float)) else 0,
    "name": _safe_scalar_str(name_candidate),
    "designation": designation_out,
    "company": _safe_scalar_str(company_candidate),
    "email": _safe_scalar_str(found_email),
    "mobile": _safe_scalar_str(found_phone),
    "website": _safe_scalar_str(found_website),
    "address": address_text if isinstance(address_text, str) else _safe_scalar_str(address_text),
    "lines": out_lines,
    "confidence": conf_val,
}
