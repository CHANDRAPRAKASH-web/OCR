company_candidate = None
for ln in structured_lines:
    s = (ln.get("text") or "").strip()
    if not s:
        continue
    if ln.get("is_contact") or ln.get("is_address_hint"):
        continue  # skip contact-like lines
    if name_candidate and s == name_candidate:
        continue
    # skip if this line is too short or obviously random (contains too many digits or punctuation)
    words = ln.get("clean_words", [])
    if len(words) < 1:
        continue
    # prefer longer non-contact lines as company
    if len(words) >= 2 or (len(words) == 1 and words[0].isalpha()):
        company_candidate = s
        break
