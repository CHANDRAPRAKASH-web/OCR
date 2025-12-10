# ------------------- build final result dict -------------------
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
            # lines: all non-empty OCR lines in reading order
            "lines": [ln.get("text", "") for ln in structured_lines if (ln.get("text") or "").strip()],
            # average confidence from tesseract raw/conf list (rounded)
            "confidence": round(_avg_confidence_from_raw(raw), 2) if 'raw' in locals() else 0.0,
        }

        return final
