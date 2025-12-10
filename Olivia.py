# tag lines (clean + flag)
for ln in structured_lines:
    s_raw = ln.get("text", "") or ""
    # 1) remove literal 'nan', 'none', 'null' at start (case-insensitive)
    s = re.sub(r'^(?:nan|none|null)[\s,:\-]*', '', s_raw, flags=re.IGNORECASE)

    # 2) remove leading non-alphanumeric junk except keep leading '+' for phone or letters for names/emails
    #    but if the leading junk is a single letter immediately followed by an email, drop it (OCR noise)
    s = re.sub(r'^[^A-Za-z0-9\+\@]+', '', s)

    # 3) sometimes OCR adds a single letter before email like "yhello@..."; remove single-letter prefix if next is an email
    s = re.sub(r'^[A-Za-z]\s+(?=[\w\.-]+@)', '', s)

    # 4) fix glued TitleCase words: "OliviaWilson" -> "Olivia Wilson"
    s = re.sub(r'([a-z])([A-Z])', r'\1 \2', s)

    # 5) collapse multiple spaces and trim
    s = re.sub(r'\s{2,}', ' ', s).strip()

    # update ln text to cleaned result
    ln["text"] = s

    # now compute flags / clean_words using cleaned text
    ln["is_contact"] = bool(is_email(s) or is_phone(s) or is_website(s))
    ln["is_address_hint"] = bool(looks_like_address(s))
    ln["clean_words"] = [w.strip(".,") for w in s.split() if w.strip(".,")]
