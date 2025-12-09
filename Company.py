def pick_name_company(lines, confs):
    entries = [{"idx": i, "text": (t or "").strip(), "conf": float(confs[i] if i < len(confs) else 0.0)} for i,t in enumerate(lines)]
    # keep only non-empty lines
    entries = [e for e in entries if e["text"]]

    # candidate name: top high-confidence line within top 6 lines that looks like title case and not contact
    def looks_like_name(s):
        parts = s.split()
        if not (1 < len(parts) <= 4): return False
        # require no digits and some capitalized tokens
        if any(any(ch.isdigit() for ch in w) for w in parts): return False
        caps = sum(1 for w in parts if w and w[0].isupper())
        return caps >= max(1, len(parts)//2)

    # filter out lines that are likely contact/website/phones
    def is_contact(s):
        return bool(EMAIL_RE.search(s) or PHONE_RE.search(s) or WEBSITE_RE.search(s))

    top_window = entries[:8]
    name = ""
    name_candidates = [e for e in top_window if looks_like_name(e["text"]) and not is_contact(e["text"])]
    if name_candidates:
        name_candidates.sort(key=lambda x: (-x["conf"], x["idx"]))
        name = name_candidates[0]["text"]

    # company: after name or the first uppercase/ALLCAPS line below name or second top line if none
    company = ""
    if name:
        idx = next((e["idx"] for e in entries if e["text"] == name), None)
        if idx is not None:
            for e in entries[idx+1: idx+6]:
                s = e["text"]
                if is_contact(s) or len(s.split()) <= 1: continue
                if any(k in s.lower() for k in ["inc", "ltd", "llc", "co", "company", "corp", "real estate", "agency"]):
                    company = s; break
            if not company:
                for e in entries[idx+1: idx+6]:
                    s = e["text"]
                    if s and s != name and not is_contact(s):
                        company = s; break
    else:
        # fallback: topmost non-contact line that looks like company
        for e in entries[:6]:
            s = e["text"]
            if s and not is_contact(s):
                company = s; break

    return name, company
