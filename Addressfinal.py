# --- SAFETY: ensure address_lines is an iterable of strings before join() ---
if not isinstance(address_lines, (list, tuple)):
    # if it's None or empty string -> treat as empty list
    if address_lines is None or (isinstance(address_lines, str) and address_lines.strip() == ""):
        address_lines = []
    else:
        # single string -> wrap into list
        address_lines = [str(address_lines)]

# Filter out any empty/None items and ensure all are strings
cleaned_address_lines = [str(a).strip() for a in address_lines if a and str(a).strip()]

# Final address text safe to join
address_text = "\n".join(cleaned_address_lines).strip()
