import re
from typing import List, Dict, Any

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
WEBSITE_RE = re.compile(r"(https?://\S+|www\.\S+)")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s\(\)]{6,}\d)")

class Recognition:
    def __init__(self, config: Dict[str,Any]=None):
        self.config = config or {}

    def extract(self, image_bytes: bytes, lang: str = "eng") -> Dict[str,Any]:
        try:
            result = self.recognize(image_bytes, lang=lang)
            lines = result.get("lines", [])
            confidences = result.get("confidences", [])
            # ensure lines is list of strings
            if lines and isinstance(lines[0], dict):
                texts = [ln.get("line_text","").strip() for ln in lines]
            else:
                texts = [str(t).strip() for t in lines if t is not None]
            # get average confidence (defensive)
            avg_conf = 0.0
            if confidences:
                try:
                    nums = [float(c) for c in confidences if c is not None and str(c).strip() not in ["", "-1"]]
                    avg_conf = (sum(nums) / len(nums)) if nums else 0.0
                except Exception:
                    avg_conf = 0.0

            extracted = self.extract_fields(texts)
            extracted["lines"] = texts
            extracted["confidence"] = round(avg_conf, 2)
            return extracted
        except Exception as e:
            return {
                "name": None,
                "designation": None,
                "company": None,
                "email": None,
                "mobile": None,
                "website": None,
                "address": None,
                "lines": [],
                "confidence": 0
            }

    def recognize(self, image_bytes: bytes, lang: str = "eng") -> Dict[str,Any]:
        """
        Run tesseract (tsv-style) and return a dict:
          {"lines": [str,...], "confidences": [float,...], "osd": ...}
        This function is defensive against different return formats from run_tesseract_data.
        """
        # call external tesseract function (must exist in your driver)
        data = run_tesseract_data(image_bytes, lang=lang)

        # Prefer TSV-style 'text' + 'conf' lists
        lines_out: List[str] = []
        confs_out: List[float] = []

        # Common keys: 'text' and 'conf' or 'left', 'top', 'width', 'height' etc.
        if isinstance(data, dict):
            # If data.get('text') is a list of tokens
            texts = data.get("text") or data.get("texts") or []
            confs = data.get("conf") or data.get("confidences") or data.get("level_conf") or []

            # If texts is a single string, split lines
            if isinstance(texts, str):
                texts = [t for t in texts.splitlines() if t.strip()]

            # If we have per-token text & conf we simply join tokens into lines heuristically:
            if isinstance(texts, list) and texts:
                # If tesseract returned TSV-level rows (some drivers give final lines already)
                # Heuristic: join tokens separated by newline characters in original 'text' if present
                # If confs length equals texts length, we can build token lines; else simple join
                if confs and len(confs) == len(texts):
                    # Build one-line-per-token list but then group contiguous tokens by newline-like tokens
                    # Simpler approach: group tokens into a single line by default
                    lines_out = [" ".join([t.strip() for t in texts if t and str(t).strip()])]
                    try:
                        confs_out = [float(x) for x in confs if x not in [None, ""]]
                    except:
                        confs_out = []
                else:
                    # texts likely already contains full lines
                    lines_out = [t.strip() for t in texts if t and str(t).strip()]
                    # try to get confidences per-line if available
                    try:
                        confs_out = [float(x) for x in (data.get("line_conf", []) or confs) if x not in [None, ""]]
                    except:
                        confs_out = []
            else:
                # fallback: convert whole raw output to one text line if available
                raw = data.get("raw", "") or data.get("raw_text", "")
                if raw:
                    lines_out = [l.strip() for l in str(raw).splitlines() if l.strip()]
                else:
                    lines_out = []
                confs_out = []
        else:
            # Unexpected type returned: string or None
            try:
                text = str(data)
                lines_out = [l.strip() for l in text.splitlines() if l.strip()]
            except:
                lines_out = []
            confs_out = []

        # Defensive cleaning
        lines_out = [l for l in lines_out if l is not None and str(l).strip() != ""]
        confs_out = [c for c in confs_out if c is not None]

        # Try to detect OSD if available (safe try)
        try:
            osd = get_osd_rotation(image_bytes)
        except Exception:
            osd = None

        return {"lines": lines_out, "confidences": confs_out, "osd": osd}

    def extract_fields(self, lines: List[str]) -> Dict[str,Any]:
        """
        Very small heuristics to extract email/phone/website/name/address from lines list.
        Returns dictionary with keys name, designation, company, email, mobile, website, address.
        """
        name = None
        designation = None
        company = None
        email = None
        mobile = None
        website = None
        address = None

        # flatten lines for easier scanning
        flat = [l for l in lines if l and str(l).strip()]
        # quick pass: email/website/phone detection
        for l in flat:
            if email is None:
                m = EMAIL_RE.search(l)
                if m:
                    email = m.group(0)
                    continue
            if website is None:
                m = WEBSITE_RE.search(l)
                if m:
                    website = m.group(0)
                    continue
            if mobile is None:
                m = PHONE_RE.search(l)
                if m:
                    mobile = re.sub(r"[^\d\+]", "", m.group(0))  # normalize digits+plus
                    continue

        # Name/Designation heuristics:
        # - If first non-empty line contains 2-3 words and they look like a person name (letters only),
        #   take it as name. Next line often designation.
        if flat:
            # try multiple candidates from top lines
            top_candidates = flat[:4]
            # pick first candidate that has alphabetic words and not email/phone/website
            for idx, cand in enumerate(top_candidates):
                if EMAIL_RE.search(cand) or WEBSITE_RE.search(cand) or PHONE_RE.search(cand):
                    continue
                # if contains many letters and fewer punctuation -> treat as name/designation
                tokens = [t for t in cand.split() if re.search(r"[A-Za-z]", t)]
                if 1 < len(tokens) <= 4 and all(re.match(r"^[A-Za-z\.\-']+$", tok) for tok in tokens):
                    name = " ".join(tokens)
                    # next line as designation (if any)
                    if idx + 1 < len(flat):
                        next_line = flat[idx + 1]
                        # avoid grabbing phone/email/website
                        if not (EMAIL_RE.search(next_line) or WEBSITE_RE.search(next_line) or PHONE_RE.search(next_line)):
                            designation = next_line.strip()
                    break

            # fallback: if no clear name found, take first alphabetic line
            if name is None:
                for cand in top_candidates:
                    if EMAIL_RE.search(cand) or WEBSITE_RE.search(cand) or PHONE_RE.search(cand):
                        continue
                    # choose candidate with mostly letters
                    if re.search(r"[A-Za-z]", cand):
                        name = cand.strip()
                        break

        # Address heuristics: look for lines with digits + street keywords or comma-contained parts
        addr_parts = []
        for l in flat[::-1]:  # scan from bottom (addresses often at bottom)
            if re.search(r"\d{1,4}\s+\w+", l) or "," in l or "St" in l or "Street" in l or "Ave" in l:
                addr_parts.insert(0, l.strip())
            # stop after collecting a couple
            if len(addr_parts) >= 3:
                break
        if addr_parts:
            address = ", ".join(addr_parts)

        return {
            "name": name,
            "designation": designation,
            "company": company,
            "email": email,
            "mobile": mobile,
            "website": website,
            "address": address
                  }
