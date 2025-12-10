# clean the raw OCR text into a safe, human string
clean_txt = robust_str(txt).strip()

# remove literal 'nan ' prefix or other literal tokens at start
if clean_txt.lower().startswith('nan '):
    clean_txt = clean_txt[4:].strip()

# if the whole token is a literal null-like string, make it empty
if clean_txt.lower() in ('nan', 'none', 'null'):
    clean_txt = ''

# normalize multiple internal whitespace and remove stray repeated punctuation
clean_txt = re.sub(r'\s+', ' ', clean_txt).strip()

structured_lines.append({
    "idx": i,
    "text": clean_txt,
    "conf": c or 0.0
})
