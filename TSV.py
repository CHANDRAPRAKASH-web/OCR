def recognize(self, image_bytes, lang="eng"):
    try:
        img = preprocess_image(image_bytes)   # keep whatever preprocessing you already have
    except Exception:
        img = image_bytes

    try:
        osd = get_osd(img)
    except Exception:
        osd = ""

    # run tesseract to get tsv-style dict (should include keys: text, left, top, width, height, conf)
    data = run_tesseract_data(img, lang=lang)

    # Build word list for TSV grouping
    word_data = []
    texts = data.get("text", [])
    lefts = data.get("left", [])
    tops = data.get("top", [])
    widths = data.get("width", [])
    heights = data.get("height", [])

    for i, t in enumerate(texts):
        if not t:
            continue
        try:
            left = int(lefts[i]) if i < len(lefts) else 0
            top = int(tops[i]) if i < len(tops) else 0
            width = int(widths[i]) if i < len(widths) else 0
            height = int(heights[i]) if i < len(heights) else 0
        except Exception:
            left = top = width = height = 0

        word_data.append({
            "text": str(t).strip(),
            "left": left,
            "top": top,
            "width": width,
            "height": height
        })

    # Group words into lines using the TSV based helper we added at top-level
    lines_grouped = group_words_by_line_using_tsv(word_data, gap_tol_px=12)

    # convert to the old form expected by your extraction logic, if necessary
    # If your existing extract_fields accepts list of lines as strings, map accordingly:
    lines_for_extract = [ln['line_text'] for ln in lines_grouped]

    # Now call your existing extract_fields (or the method that extracts name/phone/email)
    extracted = extract_fields(lines_for_extract)

    # Clean phone numbers
    if 'mobile' in extracted:
        extracted['mobile'] = [clean_phone(p) for p in extracted.get('mobile', []) if p]

    # Normalize address if you have a helper normalize_address, else simple join
    addr = extracted.get('address', '')
    if isinstance(addr, list):
        extracted['address'] = "\n".join([a for a in addr if a])
    else:
        extracted['address'] = addr or ""

    # Add OSD and other metadata
    extracted['osd'] = osd
    extracted['language_detected'] = lang

    # Final sanitize to ensure JSON serializability
    final = sanitize(extracted)

    return final
