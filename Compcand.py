company_candidate = None
if name_candidate:
    # find next line after name index
    name_idx = next((ln["idx"] for ln in structured_lines if ln["text"] == name_candidate), None)
    if name_idx is not None:
        for ln in structured_lines:
            if ln["idx"] <= name_idx:
                continue
            if ln.get("is_contact") or ln.get("is_address_hint"):
                continue
            if len(ln["text"].split()) >= 2:
                company_candidate = ln["text"]
                break
# fallback: pick the first non-contact, non-address near top
if not company_candidate:
    for ln in structured_lines:
        if ln.get("is_contact") or ln.get("is_address_hint"):
            continue
        if ln["text"] == name_candidate:
            continue
        company_candidate = ln["text"]
        break
