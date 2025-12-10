# --- Defensive final result assembly (replace existing final = { ... } ) ---
# use locals() lookups so missing/intermediate names won't crash
_name = locals().get("name_candidate", "") or ""
_designation = locals().get("designation", "") or ""
_company = locals().get("company_candidate", "") or ""
_found_email = locals().get("found_email", "") or ""
_found_phone = locals().get("found_phone", "") or ""
_found_website = locals().get("found_website", "") or ""
_address_lines = locals().get("address_lines", []) or []
_structured_lines = locals().get("structured_lines", []) or []
_raw = locals().get("raw", {}) or {}

try:
    _osd = int(osd_rotation) if isinstance(osd_rotation, (int, float, str)) else 0
except Exception:
    _osd = 0

# safe confidence extraction (if raw dict exists and has conf list)
_confidence = 0.0
try:
    if isinstance(_raw, dict):
        _confidence = round(_avg_confidence_from_raw(_raw), 2)
except Exception:
    _confidence = 0.0

final = {
    "language_detected": locals().get("lang", "") or "",
    "osd_rotation": _osd,
    "name": _name,
    "designation": _designation,
    "company": _company,
    "email": _found_email,
    "mobile": _found_phone,
    "website": _found_website,
    "address": "\n".join([a for a in _address_lines if a]).strip() if _address_lines else "",
    "lines": [ln.get("text","") for ln in _structured_lines if (ln.get("text") or "").strip()],
    "confidence": _confidence,
}
# --- end final assembly ---
