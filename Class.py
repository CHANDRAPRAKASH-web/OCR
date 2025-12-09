def recognize(self, image_bytes: bytes, lang: str = "eng") -> Dict[str, Any]:
    """
    Robust recognize: try the project's run_tesseract_data first,
    if that returns nothing useful use pytesseract.image_to_data fallback.
    Returns {"lines": [...], "confidences": [...], "osd": ...}
    """
    lines_out: List[str] = []
    confs_out: List[float] = []
    osd = None

    # --- Try the project-specific runner first (if available) ---
    try:
        data = None
        try:
            data = run_tesseract_data(image_bytes, lang=lang)
        except Exception:
            data = None

        # If data looks like a dict with 'text' key (list or str), try to use it
        if isinstance(data, dict):
            # quick debug
            print("DEBUG: run_tesseract_data returned dict keys:", list(data.keys())[:10])

            texts = data.get("text") or data.get("texts") or data.get("raw_text") or data.get("raw") or None
            confs = data.get("conf") or data.get("confidences") or data.get("line_conf") or data.get("confidence") or None

            # If texts is a single big string -> splitlines
            if isinstance(texts, str):
                lines_out = [l.strip() for l in texts.splitlines() if l.strip()]
            elif isinstance(texts, list) and texts:
                # If texts appear to be final lines already
                if all(isinstance(t, str) for t in texts):
                    lines_out = [t.strip() for t in texts if t and str(t).strip()]
                else:
                    # convert whatever to strings and join to single line as fallback
                    lines_out = [" ".join([str(t).strip() for t in texts if t and str(t).strip()])]
            else:
                # maybe the driver provided token-level fields (left/top/word)
                # attempt to build a single textual output
                if data.get("words") and isinstance(data.get("words"), list):
                    lines_out = [" ".join([str(w).strip() for w in data.get("words") if w and str(w).strip()])]
                else:
                    # fallback: try a raw text key
                    raw = data.get("raw_text") or data.get("raw") or None
                    if raw and isinstance(raw, str):
                        lines_out = [l.strip() for l in raw.splitlines() if l.strip()]

            # try to build confidences list (line-level if available)
            if confs:
                try:
                    # if confs is a list of numeric-ish values
                    if isinstance(confs, list):
                        confs_out = [float(x) for x in confs if x not in [None, ""]]
                    else:
                        confs_out = [float(confs)]
                except Exception:
                    confs_out = []
        else:
            # data not dict (maybe None or string) - treat as raw
            if isinstance(data, str):
                lines_out = [l.strip() for l in data.splitlines() if l.strip()]
            else:
                lines_out = []

    except Exception as e:
        # swallow and continue to fallback
        print("DEBUG: exception calling run_tesseract_data:", repr(e))
        lines_out = []
        confs_out = []

    # --- If nothing useful returned, fallback to pytesseract image_to_data ---
    if not lines_out:
        try:
            from PIL import Image
            import io
            import pytesseract
            from pytesseract import Output

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tsv = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT)
            # tsv has keys: level, page_num, block_num, par_num, line_num, word_num, left, top, width, height, conf, text
            # We will group words by (page_num, block_num, par_num, line_num) to make lines
            n_boxes = len(tsv.get("text", []))
            grouped = {}
            for i in range(n_boxes):
                text = str(tsv["text"][i]).strip()
                conf = tsv["conf"][i]
                if text == "" or text.lower() == " ":
                    continue
                key = (tsv.get("page_num", [1])[i], tsv.get("block_num", [0])[i], tsv.get("par_num", [0])[i], tsv.get("line_num", [0])[i])
                grouped.setdefault(key, []).append((i, text, conf))
            # produce lines in reading order
            sorted_keys = sorted(grouped.keys())
            lines_tmp = []
            confs_tmp = []
            for k in sorted_keys:
                tokens = [tok for (_idx, tok, _c) in grouped[k]]
                confs_for_line = [float(c) for (_i, _t, c) in grouped[k] if str(c).strip() not in ["-1", ""]]
                line_text = " ".join(tokens).strip()
                if line_text:
                    lines_tmp.append(line_text)
                    # average conf for that line
                    if confs_for_line:
                        confs_tmp.append(sum(confs_for_line)/len(confs_for_line))
            if lines_tmp:
                print("DEBUG: pytesseract fallback used, built", len(lines_tmp), "lines")
                lines_out = lines_tmp
                confs_out = confs_tmp
            else:
                lines_out = []
                confs_out = []
        except Exception as e:
            print("DEBUG: pytesseract fallback failed:", repr(e))
            lines_out = []
            confs_out = []

    # Attempt to get OSD rotation if available
    try:
        osd = get_osd_rotation(image_bytes)
    except Exception:
        osd = None

    # final defensive cleaning
    lines_out = [l for l in lines_out if l and str(l).strip()]
    confs_out = [c for c in confs_out if c is not None]

    return {"lines": lines_out, "confidences": confs_out, "osd": osd}
