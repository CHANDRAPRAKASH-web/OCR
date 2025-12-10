# ========== DEBUG: dump tesseract outputs (temporary) ==========
try:
    print("DEBUG: run_tesseract_data type:", type(data))
    print("DEBUG: keys:", list(data.keys()))
    txt_list = data.get("text", [])
    conf_list = data.get("conf", [])
    raw = data.get("raw", {})
    print("DEBUG: len(text) =", len(txt_list))
    print("DEBUG: len(conf) =", len(conf_list))
    # print first 12 text/conf items for inspection
    for i, t in enumerate(txt_list[:12]):
        c = conf_list[i] if i < len(conf_list) else None
        print(f"DEBUG: text[{i!s}]: {repr(t)}  conf[{i!s}]: {repr(c)}")
    # if there is a 'raw' or nested 'text' in raw, print keys
    if isinstance(raw, dict):
        print("DEBUG: raw keys:", list(raw.keys()))
        if "text" in raw:
            print("DEBUG: first 6 raw['text']:", [repr(x) for x in raw.get("text", [])[:6]])
except Exception as _dbg_e:
    print("DEBUG: error dumping tesseract data:", _dbg_e)
# ==============================================================
