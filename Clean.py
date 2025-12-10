# ----- CLEAN & NORMALIZE TEXT LINES (small fixes, keep original vars) -----
import unicodedata
_camel_split_re = re.compile(r'([a-z])([A-Z])')   # to separate "OliviaWilson" -> "Olivia Wilson"
_leading_nan_re = re.compile(r'^(?:nan|none|null|nan,|\-)+\s*', re.I)  # remove leading nan/null junk
_nonprint_re = re.compile(r'[\x00-\x1f\x7f]+')  # control chars

for ln in structured_lines:
    txt = ln.get("text", "") or ""
    # normalize unicode and remove control chars
    try:
        txt = unicodedata.normalize("NFKC", txt)
    except Exception:
        pass
    txt = _nonprint_re.sub(" ", txt)

    # remove repeating 'nan' or other literal tokens at start (OCR artifact)
    txt = _leading_nan_re.sub("", txt).strip()

    # if text begins with stray non-alnum characters (like stray 'y' or punctuation),
    # but contains an email later, remove leading single non-alpha char only when it
    # is immediately before an alpha (covers "yhello@..." -> "hello@...")
    if txt and not txt[0].isalnum():
        # keep single leading '+' (phone international)
        if not txt.startswith('+'):
            if EMAIL_RE.search(txt):
                # remove only leading non-alnum chars
                txt = re.sub(r'^[^A-Za-z0-9@+]+', '', txt)
            else:
                txt = re.sub(r'^[^A-Za-z0-9+]+', '', txt)

    # split camel-case TitleCase merges: "OliviaWilson" -> "Olivia Wilson"
    # but only if the token looks like a name (no digits, has uppercase transitions)
    if txt and re.search(r'[A-Z][a-z]+[A-Z][a-z]+', txt):
        txt = _camel_split_re.sub(r'\1 \2', txt)

    # collapse multi-space and trim
    txt = re.sub(r'\s{2,}', ' ', txt).strip()

    # replace solitary repeated punctuation/comma sequences that break tokens
    txt = re.sub(r'[,;:\-]{2,}', ',', txt)

    # final fallback: convert literal "nan" words to empty
    if txt.lower() in ("nan", "none", "null"):
        txt = ""

    # ensure confidence is a number (0 if missing)
    try:
        ln["conf"] = float(ln.get("conf") or 0.0)
    except Exception:
        ln["conf"] = 0.0

    ln["text"] = txt
    ln["clean_words"] = [w.strip(".,;:!()[]") for w in txt.split() if w.strip(".,;:!()[]")]
