structured_lines = []

for i, txt in enumerate(lines_raw):
    # confidence for this line
    try:
        c = float(conf_list[i]) if i < len(conf_list) else 0.0
    except:
        c = 0.0

    clean_txt = robust_str(txt).strip()

    # remove leading nan/null/etc
    if clean_txt.lower().startswith("nan "):
        clean_txt = clean_txt[4:].strip()

    if clean_txt.lower() in ("nan", "none", "null"):
        clean_txt = ""

    clean_txt = re.sub(r"\s+", " ", clean_txt).strip()

    structured_lines.append({
        "idx": i,
        "text": clean_txt,
        "conf": c
    })
