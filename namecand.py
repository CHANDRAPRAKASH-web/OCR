# select name candidate: prefer top-of-card, titlecase, shortish (1-3 words), no digits
name_candidate = None
possible = []
for ln in structured_lines:
    s = ln["text"]
    if not s:
        continue
    if ln.get("is_contact") or ln.get("is_address_hint"):
        continue
    words = [w for w in s.split() if w]
    if not (1 <= len(words) <= 4):
        continue
    if any(ch.isdigit() for ch in s):
        continue
    # titlecase ratio (prefer lines with capital letters)
    tc = sum(1 for w in words if w[0].isupper())
    if tc >= 1:
        possible.append((ln["idx"], ln["conf"], s))
# choose top-most highest-confidence candidate
if possible:
    possible.sort(key=lambda x: (x[0], -x[1]))   # prefer earlier line index, then higher conf
    name_candidate = possible[0][2]
