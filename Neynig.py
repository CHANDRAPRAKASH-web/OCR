# --- final output (replace any call to final_clean(...) with this block) ---
# Ensure the variable names used below match the ones computed earlier in this function.
# If your variable names differ, replace them accordingly.

final = {
    "language_detected": lang if 'lang' in locals() else None,
    "osd_rotation": int(osd_rotation) if 'osd_rotation' in locals() and osd_rotation is not None else 0,
    "name": (name_candidate if 'name_candidate' in locals() else "") or "",
    "designation": (designation if 'designation' in locals() else "") or "",
    "company": (company_candidate if 'company_candidate' in locals() else "") or "",
    "email": (found_email if 'found_email' in locals() else "") or "",
    "mobile": (found_phone if 'found_phone' in locals() else "") or "",
    "website": (found_website if 'found_website' in locals() else "") or "",
    "address": (address_text.strip() if 'address_text' in locals() and address_text else "") or "",
    # lines: ensure we return plain strings list (avoid None)
    "lines": [ (ln.get("text","") if isinstance(ln, dict) else (ln or "")) for ln in (structured_lines if 'structured_lines' in locals() and structured_lines else []) ],
    # confidence: average of conf_list if available, else 0.0
    "confidence": (
        round(float(sum(conf_list))/len(conf_list), 2)
        if ('conf_list' in locals() and conf_list and len(conf_list) > 0)
        else 0.0
    )
}

# Always return the final dict from extract()
return final
