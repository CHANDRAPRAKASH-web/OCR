# --- build final output dict (ensure same field names as before) ---
        final = {
            "language_detected": lang,
            "osd_rotation": osd_rotation,
            "name": name_candidate or "",
            "designation": designation or "",
            "company": company_candidate or "",
            "email": found_email or "",
            "mobile": found_phone or "",
            "website": found_website or "",
            "address": "\n".join(address_lines).strip() if address_lines else "",
            # include only non-empty cleaned lines
            "lines": [ln["text"] for ln in structured_lines if (ln.get("text") or "").strip()],
            "confidence": round(_avg_confidence_from_raw(raw), 2) if raw else 0.0,
            # keep raw if you want it for debugging; remove or sanitize if too large
            "raw": raw if isinstance(raw, dict) else None
        }

        # debug print: (optional, remove later if too verbose)
        try:
            print("DEBUG(extract): final keys:", list(final.keys()))
            print("DEBUG(extract): name,email,mobile ->", final["name"], final["email"], final["mobile"])
            print("DEBUG(extract): address preview ->", repr(final["address"])[:120])
        except Exception:
            pass

        return final
