# --- run tesseract once and keep both "text" (lines) and raw image_to_data dict ---
try:
    # prefer driver.run_tesseract_data if available
    if hasattr(driver, "run_tesseract_data"):
        data = driver.run_tesseract_data(pre, lang=lang)
    else:
        data = run_tesseract_data(pre, lang=lang)
except Exception as e:
    print("ERROR in tesseract:", repr(e))
    data = {}

# ensure data is a dict
if not isinstance(data, dict):
    data = {}

# structured access
lines_raw = data.get("text", []) or []
raw = data.get("raw", {}) or {}
conf_list = raw.get("conf", []) if isinstance(raw, dict) else []
# --- end of stable assignment ---
