def extract(self, image_bytes, lang="eng"):
        try:
            osd_rotation = driver.get_osd_rotation(image_bytes)
        except Exception:
            osd_rotation = 0

        data = driver.run_tesseract_data(image_bytes, lang=lang)
        # data expected structure:
        # data["text"] -> list of lines (strings)
        # data["raw"]  -> raw tesseract image_to_data dict (with 'conf' etc)
        lines_raw = data.get("text", []) or []
        raw = data.get("raw", {}) or {}

        # build lines with confidences (if available)
        conf_list = raw.get("conf", [])
        structured_lines = []
        for i, txt in enumerate(lines_raw):
            c = None
            try:
                c = float(conf_list[i]) if i < len(conf_list) else None
            except Exception:
                c = None
            structured_lines.append({"idx": i, "text": (txt or "").strip(), "conf": c or 0.0})

        # helper markers
        def is_email(s): return EMAIL_RE.search(s) is not None
        def is_phone(s): return PHONE_RE.search(s) is not None
        def is_website(s): return WEBSITE_RE.search(s) is not None
        def looks_like_address(s):
            low = s.lower()
            if ZIP_RE.search(s): 
                return True
            if any(k in low for k in STREET_KEYWORDS):
                # ensure it's not a tiny single word like "St"
                if len(s.split()) >= 2:
                    return True
            # house number + street word pattern e.g. "123 Main St"
            if re.search(r'\b\d{1,5}\b.*\b(?:' + '|'.join(STREET_KEYWORDS) + r')\b', low):
                return True
            return False

        # tag lines
        for ln in structured_lines:
            s = ln["text"]
            ln["is_contact"] = bool(is_email(s) or is_phone(s) or is_website(s))
            ln["is_address_hint"] = bool(looks_like_address(s))
            ln["clean_words"] = [w.strip(".,") for w in s.split() if w.strip(".,")]

        # extract contact info first
        found_email = None
        found_phone = None
        found_website = None
        for ln in structured_lines:
            s = ln["text"]
            if not found_email and is_email(s):
                found_email = EMAIL_RE.search(s).group(0)
            if not found_phone and is_phone(s):
                found_phone = _clean_phone(PHONE_RE.search(s).group(0))
            if not found_website and is_website(s):
                found_website = WEBSITE_RE.search(s).group(0)

        # find contiguous address block starting from any address hint near bottom
        address_lines = []
        if any(ln["is_address_hint"] for ln in structured_lines):
            # prefer address hints near bottom (business cards typically have address lower)
            candidates = [ln for ln in structured_lines if ln["is_address_hint"]]
            # pick the lowest (max idx)
            anchor = max(candidates, key=lambda x: x["idx"])
            i = anchor["idx"]
            # expand upward and downward while contiguous and not contact
            # upward
            j = i
            while j >= 0:
                ln = structured_lines[j]
                if ln["is_contact"]:
                    break
                if ln["text"] == "":
                    # allow one empty line break but stop if many
                    j -= 1
                    continue
                address_lines.insert(0, ln["text"])
                j -= 1
                # stop if we've added >4 lines
                if len(address_lines) >= 4:
                    break
            # if too many non-address lines added, prune using address hint requirement
            # (we keep as-is for now)

        # find designation (anywhere)
        designation = None
        for ln in structured_lines:
            low = ln["text"].lower()
            if any(k in low for k in DESIGNATION_KEYWORDS):
                designation = ln["text"]
                break

        # find name candidate
        name_candidate = None
        # heuristics: short (2-3 words), TitleCase words (start with uppercase), no digits, not contact, not address
        possible = []
        for ln in structured_lines:
            s = ln["text"]
            if not s or ln["is_contact"] or ln["is_address_hint"]:
                continue
            words = ln["clean_words"]
            if 2 <= len(words) <= 3:
                if any(ch.isdigit() for ch in s):
                    continue
                # check Title-case ratio
                tc = sum(1 for w in words if w and w[0].isupper())
                if tc >= 1:
                    possible.append(ln)
        # prefer highest confidence among possibles and earlier lines (top of card)
        if possible:
            possible.sort(key=lambda x: (-x["conf"], x["idx"]))
            name_candidate = possible[0]["text"]

        # company candidate: first non-contact/non-address line near the top if not name
        company_candidate = None
        for ln in structured_lines:
            s = ln["text"]
            if not s or ln["is_contact"] or ln["is_address_hint"]:
                continue
            if name_candidate and s == name_candidate:
                continue
            # Skip if likely designation
            if designation and s == designation:
                continue
            # choose a longer line >2 words as company
            if len(ln["clean_words"]) >= 1:
                company_candidate = s
                break

        final = {
            "language_detected": lang,
            "osd_rotation": osd_rotation,
            "name": name_candidate or "",
            "designation": designation or "",
            "company": company_candidate or "",
            "email": found_email or "",
            "mobile": found_phone or "",
            "website": found_website or "",
            "address": "\n".join(address_lines).strip(),
            "lines": [ln["text"] for ln in structured_lines],
            "confidence": round(_avg_confidence_from_raw(raw), 2),
            "raw": raw
        }
        return final
