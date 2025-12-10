# ---------- improved heuristics: designation / name / company ----------
        designation = None
        # prefer explicit keyword matches in non-contact lines (search from top down)
        for ln in structured_lines:
            s = (ln.get("text") or "").strip()
            if not s or ln.get("is_contact") or ln.get("is_address_hint"):
                continue
            low = s.lower()
            for kw in DESIGNATION_KEYWORDS:
                if kw in low.split():
                    designation = s
                    break
            if designation:
                break

        # name candidate: prefer short Title-Case-looking lines near top that are NOT contact/address
        name_candidate = None
        possible = []
        for ln in structured_lines:
            s = (ln.get("text") or "").strip()
            if not s or ln.get("is_contact") or ln.get("is_address_hint"):
                continue
            words = [w for w in ln.get("clean_words", []) if w]
            if 1 <= len(words) <= 3:
                # reject if words contain obvious website tokens or digits
                if any(EMAIL_RE.search(w) or WEBSITE_RE.search(w) or any(ch.isdigit() for ch in w) for w in words):
                    continue
                # count Title-case words
                tc = sum(1 for w in words if w and w[0].isupper())
                if tc >= 1:
                    possible.append(ln)
        if possible:
            # prefer earlier lines and higher confidence
            possible.sort(key=lambda x: (x.get("idx", 9999), -float(x.get("conf", 0.0))))
            name_candidate = possible[0].get("text")

        # company candidate: pick the first non-contact/non-address line from very top,
        # but avoid accidentally picking name (if equal) or designation or a short noisy token.
        company_candidate = None
        for ln in structured_lines:
            s = (ln.get("text") or "").strip()
            if not s or ln.get("is_contact") or ln.get("is_address_hint"):
                continue
            if name_candidate and s == name_candidate:
                continue
            if designation and s == designation:
                continue
            # require at least 2 characters and not only symbols
            if len(re.sub(r'[\W_]+', '', s)) < 2:
                continue
            # avoid picking pure URLs or phone-like tokens
            if WEBSITE_RE.search(s) or PHONE_RE.search(s) or EMAIL_RE.search(s):
                continue
            company_candidate = s
            break

        # If company still empty, fallback to first website stripped of protocol (rare)
        if not company_candidate and found_website:
            company_candidate = re.sub(r'https?://', '', found_website).split('/')[0]

        # Build final output dict (consistent keys & safe values)
        final = {
            "language_detected": lang,
            "osd_rotation": int(osd_rotation) if osd_rotation is not None else 0,
            "name": name_candidate or "",
            "designation": designation or "",
            "company": company_candidate or "",
            "email": found_email or "",
            "mobile": found_phone or "",
            "website": found_website or "",
            "address": "\n".join(address_lines).strip() if address_lines else "",
            "lines": [ln.get("text", "") for ln in structured_lines if (ln.get("text") or "").strip()],
            "confidence": round(_avg_confidence_from_raw(raw), 2) if isinstance(raw, dict) else 0.0,
        }

        return final
