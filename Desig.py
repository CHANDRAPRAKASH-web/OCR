# ---------- finalize heuristics: designation, name, company, confidence ----------
# Find designation (if any) - common job words
designation = None
for ln in structured_lines:
    low = (ln.get("text") or "").lower()
    if any(k in low for k in DESIGNATION_KEYWORDS):
        designation = ln.get("text")
        break

# Find contact candidates already discovered earlier: found_email, found_phone, found_website
# (these variables were set in the contact-extraction loop above)

# Name candidate: prefer a short (2-3 words), title-cased line, not contact, not address
name_candidate = None
candidates = []
for ln in structured_lines:
    text = (ln.get("text") or "").strip()
    if not text:
        continue
    if ln.get("is_contact") or ln.get("is_address_hint"):
        continue
    words = [w for w in ln.get("clean_words", []) if w]
    if 2 <= len(words) <= 3:
        # prefer lines without digits and some TitleCase signal
        if any(ch.isdigit() for ch in text):
            continue
        tc = sum(1 for w in words if w and w[0].isupper())
        candidates.append((ln.get("conf", 0.0), ln.get("idx", 0), tc, text, ln))

# sort by confidence desc, then earlier idx, then titlecase count
if candidates:
    candidates.sort(key=lambda x: (-float(x[0] or 0.0), int(x[1] or 0), -int(x[2] or 0)))
    name_candidate = candidates[0][3]

# Company candidate: pick first non-contact/non-address line near top that is not the name and not a designation
company_candidate = None
for ln in structured_lines:
    text = (ln.get("text") or "").strip()
    if not text or ln.get("is_contact") or ln.get("is_address_hint"):
        continue
    if name_candidate and text == name_candidate:
        continue
    if designation and text == designation:
        continue
    # prefer a line with > =1 words (company names can be 1 word too)
    words = [w for w in ln.get("clean_words", []) if w]
    if words:
        company_candidate = text
        break

# If no company found but name looks like company (single long token), try to use that
if not company_candidate and name_candidate:
    if len(name_candidate.split()) >= 2:
        # keep as name, not company
        pass

# If we found nothing, try to fallback to the first non-empty structured line
if not name_candidate:
    for ln in structured_lines:
        t = (ln.get("text") or "").strip()
        if t and not ln.get("is_contact") and not ln.get("is_address_hint"):
            name_candidate = t
            break

# Format final values, ensuring safe strings
def _safe_str(x):
    return "" if x is None else str(x)

final = {
    "language_detected": lang,
    "osd_rotation": int(osd_rotation) if isinstance(osd_rotation, (int, float)) else 0,
    "name": _safe_str(name_candidate or ""),
    "designation": _safe_str(designation or ""),
    "company": _safe_str(company_candidate or ""),
    "email": _safe_str(found_email or ""),
    "mobile": _safe_str(found_phone or ""),
    "website": _safe_str(found_website or ""),
    "address": "\n".join(address_lines).strip(),
    "lines": [ln.get("text") for ln in structured_lines if (ln.get("text") or "").strip()],
    "confidence": round(_avg_confidence_from_raw(raw), 2) if isinstance(raw, dict) else 0.0,
}
return final
