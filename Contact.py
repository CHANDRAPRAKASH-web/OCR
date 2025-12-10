# --- immediately after building structured_lines list (before name/company heuristics) ---
# extract contact info first from the structured_lines and remove those tokens from text
found_email = None
found_phone = None
found_website = None

for ln in structured_lines:
    s = ln.get("text", "") or ""
    # email
    if not found_email:
        m = EMAIL_RE.search(s)
        if m:
            found_email = m.group(0)
            # remove email token from line text
            ln["text"] = s.replace(found_email, "").strip()
            s = ln["text"]
    # website
    if not found_website:
        m = WEBSITE_RE.search(s)
        if m:
            found_website = m.group(0)
            ln["text"] = ln["text"].replace(found_website, "").strip()
            s = ln["text"]
    # phone
    if not found_phone:
        m = PHONE_RE.search(s)
        if m:
            rawp = m.group(0)
            found_phone = _clean_phone(rawp)
            ln["text"] = ln["text"].replace(rawp, "").strip()
            s = ln["text"]

# sanity: if found_phone is raw digits (not formatted), run clean_phone to format using region
if found_phone and not found_phone.startswith('+'):
    formatted = clean_phone(found_phone)
    if formatted:
        found_phone = formatted
