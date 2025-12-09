def recognize(self, image_bytes: bytes, lang: str = "eng") -> Dict[str, Any]:
    """
    Diagnostic recognize:
    - print exactly what run_tesseract_data(...) returns (type + small repr)
    - try to extract text if driver returned a reasonable structure
    - fallback to pytesseract.image_to_data if needed
    """
    lines_out: List[str] = []
    confs_out: List[float] = []
    osd = None

    # 1) Run project's driver and *print* exactly what it returns (for debugging)
    driver_result = None
    try:
        driver_result = run_tesseract_data(image_bytes, lang=lang)
    except Exception as e:
        print("DEBUG: run_tesseract_data raised exception:", repr(e))
        driver_result = None

    # Print debug summary (important: paste this output back here if still broken)
    try:
        print("DEBUG: run_tesseract_data type:", type(driver_result))
        # show a safe short repr (avoid huge prints)
        repr_sample = repr(driver_result)
        if len(repr_sample) > 1000:
            repr_sample = repr_sample[:1000] + " ...[truncated]"
        print("DEBUG: run_tesseract_data repr:", repr_sample)
    except Exception as e:
        print("DEBUG: failed to repr driver_result:", repr(e))

    # 2) Try to use driver's output if it looks like dict/list/string
    if isinstance(driver_result, dict):
        # common keys we might expect
        text_candidates = []
        for candidate_key in ("text", "texts", "raw_text", "raw", "ocr_text"):
            if candidate_key in driver_result:
                text_candidates.append(driver_result[candidate_key])
        # prefer 'text' then fallback to other keys
        chosen_text = text_candidates[0] if text_candidates else None

        # if driver provided token-level fields similar to tsv-style
        if chosen_text:
            if isinstance(chosen_text, str):
                lines_out = [l.strip() for l in chosen_text.splitlines() if l.strip()]
            elif isinstance(chosen_text, list):
                lines_out = [str(x).strip() for x in chosen_text if x and str(x).strip()]
        else:
            # try to assemble from possible token fields (words/left/top/conf/text)
            if "text" in driver_result and isinstance(driver_result["text"], list):
                lines_out = [str(x).strip() for x in driver_result["text"] if x and str(x).strip()]
            elif "words" in driver_result and isinstance(driver_result["words"], list):
                # join token list into one line as fallback
                lines_out = [" ".join([str(w).strip() for w in driver_result["words"] if w and str(w).strip()])]
            else:
                # last try: any top-level string values joined
                joined = []
                for k, v in driver_result.items():
                    if isinstance(v, str) and v.strip():
                        joined.append(v.strip())
                if joined:
                    lines_out = ["\n".join(joined)]

        # try confidences
        conf_val = None
        for ck in ("conf", "confidence", "confidences", "line_conf"):
            if ck in driver_result:
                conf_val = driver_result[ck]
                break
        if conf_val is not None:
            try:
                if isinstance(conf_val, list):
                    confs_out = [float(x) for x in conf_val if x not in (None, "", "nan")]
                else:
                    confs_out = [float(conf_val)]
            except Exception:
                confs_out = []

    elif isinstance(driver_result, list):
        # maybe driver returned list of lines
        lines_out = [str(x).strip() for x in driver_result if x and str(x).strip()]
    elif isinstance(driver_result, str):
        lines_out = [l.strip() for l in driver_result.splitlines() if l.strip()]

    # 3) If driver's output was empty or unusable -> fallback to pytesseract
    if not lines_out:
        try:
            from PIL import Image
            import io
            import pytesseract
            from pytesseract import Output

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            tsv = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT)
            n = len(tsv.get("text", []))
            grouped = {}
            for i in range(n):
                t = str(tsv["text"][i]).strip()
                if not t:
                    continue
                key = (tsv.get("page_num", [1])[i],
                       tsv.get("block_num", [0])[i],
                       tsv.get("par_num", [0])[i],
                       tsv.get("line_num", [0])[i])
                grouped.setdefault(key, []).append((i, t, tsv.get("conf", [])[i] if "conf" in tsv else -1))
            sorted_keys = sorted(grouped.keys())
            lines_tmp = []
            confs_tmp = []
            for k in sorted_keys:
                tokens = [tok for (_idx, tok, _c) in grouped[k]]
                confs_for_line = [float(c) for (_i, _t, c) in grouped[k] if str(c).strip() not in ("-1", "")]
                line_text = " ".join(tokens).strip()
                if line_text:
                    lines_tmp.append(line_text)
                    confs_tmp.append(sum(confs_for_line)/len(confs_for_line) if confs_for_line else 0.0)
            lines_out = lines_tmp
            confs_out = confs_tmp
            print("DEBUG: fallback pytesseract produced", len(lines_out), "lines")
        except Exception as e:
            print("DEBUG: pytesseract fallback failed:", repr(e))
            lines_out = []
            confs_out = []

    # 4) osd/rotation if available (best-effort)
    try:
        osd = get_osd_rotation(image_bytes)
    except Exception:
        osd = None

    # 5) final cleanup
    lines_out = [l for l in lines_out if l and str(l).strip()]
    confs_out = [float(c) for c in confs_out if c is not None] if confs_out else []

    # show final debug state (paste this if still wrong)
    print("DEBUG: final lines count:", len(lines_out), "final confs count:", len(confs_out))

    return {"lines": lines_out, "confidences": confs_out, "osd": osd}
