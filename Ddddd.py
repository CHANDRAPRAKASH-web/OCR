# ---- Finalize: choose name / company / designation / address / lines / confidence ----

# helper: safe string
def _safe_str(x):
    return "" if x is None else str(x)

# ensure raw exists for confidence calculation
_raw = raw if isinstance(raw, dict) else {}

# collect lines in original order (cleaned text)
lines_texts = [ln.get("text","").strip() for ln in structured_lines if (ln.get("text") or "").strip()]

# pick designation: first line containing a designation keyword
designation = None
for ln in structured_lines:
    txt = (ln.get("text") or "").strip()
    if not txt:
        continue
    low = txt.lower()
    if any(k in low for k in DESIGNATION_KEYWORDS):
        designation = txt
        break

# pick name: first short (1-3 words) title-like line near top that is not contact/address
name_candidate = None
for ln in structured_lines:
    txt = (ln.get("text") or "").strip()
    if not txt:
        continue
    if ln.get("is_contact") or ln.get("is_address_hint"):
        continue
    words = [w for w in ln.get("clean_words", []) if w]
    if 1 <= len(words) <= 3:
        # avoid lines with many digits
        if any(ch.isdigit() for ch in txt):
            continue
        # require at least one Title-case signal or all-caps (company-like will often be all-caps but often >3 words)
        if any(w and w[0].isupper() for w in words) or txt.isupper():
            name_candidate = txt
            break

# fallback name: first non-contact non-address line
if not name_candidate:
    for ln in structured_lines:
        txt = (ln.get("text") or "").strip()
        if not txt:
            continue
        if ln.get("is_contact") or ln.get("is_address_hint"):
            continue
        name_candidate = txt
        break

# pick company: prefer the next non-contact/non-address line after name, or the top-most non-contact that's different
company_candidate = None
if name_candidate:
    # find index of name in structured_lines
    idx_map = {ln.get("idx", i): i for i, ln in enumerate(structured_lines)}
    # brute force: find first occurrence by text match & then pick subsequent line
    found_index = None
    for i, ln in enumerate(structured_lines):
        if (ln.get("text") or "").strip() == name_candidate:
            found_index = i
            break
    if found_index is not None:
        for j in range(found_index + 1, len(structured_lines)):
            ln2 = structured_lines[j]
            t2 = (ln2.get("text") or "").strip()
            if not t2:
                continue
            if ln2.get("is_contact") or ln2.get("is_address_hint"):
                continue
            if t2 != name_candidate and (designation is None or t2 != designation):
                company_candidate = t2
                break
# fallback: first non-contact non-address line not equal to name_candidate
if not company_candidate:
    for ln in structured_lines:
        t = (ln.get("text") or "").strip()
        if not t:
            continue
        if ln.get("is_contact") or ln.get("is_address_hint"):
            continue
        if t != name_candidate and (designation is None or t != designation):
            company_candidate = t
            break

# address: prefer the address_lines that were assembled earlier; if empty, try to join trailing lines that look like addresses
address_text = "\n".join(address_lines).strip() if address_lines else ""
if not address_text:
    # try scanning for address-like lines near bottom
    addr_parts = []
    for ln in reversed(structured_lines[-6:]):  # last up to 6 lines
        t = (ln.get("text") or "").strip()
        if not t:
            continue
        if ln.get("is_contact"):
            continue
        if _line_has_address_hint(t) or re.search(r'\d{3,}', t):
            addr_parts.insert(0, t)
    address_text = ", ".join(addr_parts).strip()

# ensure phone/website/email are safe strings (found_phone/website/email expected to exist)
mobile_safe = _safe_str(found_phone or "")
website_safe = _safe_str(found_website or "")
email_safe = _safe_str(found_email or "")

final = {
    "language_detected": lang,
    "osd_rotation": int(osd_rotation) if isinstance(osd_rotation, (int, float)) else 0,
    "name": _safe_str(name_candidate or ""),
    "designation": _safe_str(designation or ""),
    "company": _safe_str(company_candidate or ""),
    "email": email_safe,
    "mobile": mobile_safe,
    "website": website_safe,
    "address": address_text or "",
    "lines": lines_texts,
    "confidence": round(_avg_confidence_from_raw(_raw), 2) if isinstance(_raw, dict) else 0.0,
}
return final
