# --- DEBUG CHECK: ensure tesseract output is correct ---
try:
    if hasattr(driver, "run_tesseract_data"):
        data = driver.run_tesseract_data(pre, lang=lang)
    else:
        data = run_tesseract_data(pre, lang=lang)

    print("DEBUG: run_tesseract_data type:", type(data))
    if isinstance(data, dict):
        print("DEBUG: keys:", list(data.keys()))
        for k in ("text", "left", "top", "width", "height", "conf", "raw"):
            if k in data:
                v = data[k]
                if isinstance(v, (list, tuple)):
                    print(f"DEBUG: len({k}) =", len(v))
                else:
                    print(f"DEBUG: {k} type =", type(v))
    else:
        print("DEBUG: NOT A DICT:", data)

except Exception as e:
    print("ERROR in tesseract:", repr(e))
    data = {}
# --- END DEBUG ---
