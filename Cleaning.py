# quick cleanup: drop lines that are now empty, or strip obvious junk sequences
cleaned_structured = []
for ln in structured_lines:
    txt = (ln.get("text") or "").strip()
    # drop empty or too-short noise-only lines
    if not txt:
        continue
    # remove repeated backslashes / excessive punctuation leftover
    txt = re.sub(r'[\\]{2,}', '', txt)
    txt = re.sub(r'[_\-\.\s]{2,}', ' ', txt)
    ln["text"] = txt.strip()
    cleaned_structured.append(ln)
structured_lines = cleaned_structured
