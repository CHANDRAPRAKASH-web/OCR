def _final_clean(s):
    if not s:
        return ""
    st = str(s).strip()
    st = st.replace('\\n', ' ').replace('\\r', ' ')
    st = re.sub(r'\\+', '', st)      # remove excess backslashes
    st = re.sub(r'\s{2,}', ' ', st).strip()
    return st

# update final to apply to string fields:
final = {
    "language_detected": lang,
    "osd_rotation": osd_rotation,
    "name": _final_clean(name_candidate or ""),
    "designation": _final_clean(designation or ""),
    "company": _final_clean(company_candidate or ""),
    "email": _final_clean(found_email or ""),
    "mobile": _final_clean(found_phone or ""),
    "website": _final_clean(found_website or ""),
    "address": _final_clean(address_text or ""),
    "lines": [ _final_clean(ln["text"]) for ln in structured_lines if (ln.get("text") or "").strip() ],
    "confidence": round(_avg_confidence_from_raw(raw), 2),
}
