import re
import math
import io
from typing import List, Dict, Any, Optional

from PIL import Image
import numpy as np
import pytesseract

try:
    from tesseract_driver import run_tesseract_data, get_osd_rotation
except Exception:
    # fallback to pytesseract directly if local module not found
    run_tesseract_data = None
    get_osd_rotation = None


EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.I)
WWW_RE = re.compile(r'((?:https?://)?(?:www\.)?[\w\.-]+\.\w{2,}(?:/[\w\-\._~:/?#[\]@!$&\'()+,;=%])?)', re.I)
PHONE_RE = re.compile(r'(\+?\d{1,3}[\s\-]?)?(?:\(?\d{1,4}\)?[\s\-]?)?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{2,4}', re.I)
STREET_KEYWORDS = ['street', 'st', 'road', 'rd', 'ave', 'avenue', 'blvd', 'lane', 'ln', 'suite', 'ste', 'floor', 'fl', 'road', 'drive', 'dr', 'park', 'plaza', 'way', 'boulevard']


class Recognition:
    def _init_(self, tesseract_cmd: Optional[str] = None):
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    def _to_pil(self, image_bytes: Any) -> Image.Image:
        if isinstance(image_bytes, Image.Image):
            return image_bytes
        if isinstance(image_bytes, (bytes, bytearray)):
            return Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if isinstance(image_bytes, np.ndarray):
            return Image.fromarray(image_bytes)
        raise ValueError("Unsupported image input type")

    def _run_tsv(self, pil_img: Image.Image, lang: str = "eng") -> Dict[str, List]:
        if run_tesseract_data is not None:
            data = run_tesseract_data(pil_img, lang=lang)
            return data
        # fallback using pytesseract.image_to_data
        raw = pytesseract.image_to_data(pil_img, lang=lang, output_type=pytesseract.Output.DICT)
        # normalize keys to expected names
        out = {
            "text": raw.get("text", []),
            "left": raw.get("left", []),
            "top": raw.get("top", []),
            "width": raw.get("width", []),
            "height": raw.get("height", []),
            "conf": raw.get("conf", []),
        }
        return out

    def _group_words_to_lines(self, data: Dict[str, List]) -> List[Dict[str, Any]]:
        texts = data.get("text", [])
        lefts = data.get("left", [])
        tops = data.get("top", [])
        widths = data.get("width", [])
        heights = data.get("height", [])
        confs = data.get("conf", [])

        items = []
        for i, t in enumerate(texts):
            txt = (t or "").strip()
            if txt == "":
                continue
            try:
                l = int(lefts[i])
                tpos = int(tops[i])
                w = int(widths[i]) if i < len(widths) else 0
                h = int(heights[i]) if i < len(heights) else 0
            except Exception:
                continue
            c = None
            try:
                c = float(confs[i])
            except Exception:
                c = None
            items.append({"text": txt, "left": l, "top": tpos, "width": w, "height": h, "conf": c})

        if not items:
            return []

        items.sort(key=lambda x: (x["top"], x["left"]))

        lines = []
        current = {"top": items[0]["top"], "items": [items[0]]}
        for it in items[1:]:
            if abs(it["top"] - current["top"]) <= max(10, int(it.get("height", 0) * 0.6)):
                current["items"].append(it)
                current["top"] = int(sum(i["top"] for i in current["items"]) / len(current["items"]))
            else:
                lines.append(current)
                current = {"top": it["top"], "items": [it]}
        lines.append(current)

        out_lines = []
        for ln in lines:
            parts = sorted(ln["items"], key=lambda x: x["left"])
            line_text = " ".join(p["text"] for p in parts).strip()
            avg_conf = None
            confs_list = [p["conf"] for p in parts if p.get("conf") is not None and not math.isnan(p["conf"])]
            if confs_list:
                try:
                    avg_conf = float(sum(confs_list) / len(confs_list))
                except Exception:
                    avg_conf = None
            out_lines.append({"text": line_text, "items": parts, "conf": avg_conf})
        return out_lines

    def _choose_phone(self, text_lines: List[str]) -> Optional[str]:
        candidates = []
        for t in text_lines:
            for m in PHONE_RE.findall(t):
                num = re.sub(r'[^\d+]', '', m)
                if len(re.sub(r'\D', '', num)) >= 7:
                    candidates.append(num)
        if not candidates:
            return None
        # choose longest / first
        candidates = sorted(candidates, key=lambda x: -len(re.sub(r'\D', '', x)))
        return candidates[0]

    def _choose_email(self, text_lines: List[str]) -> Optional[str]:
        for t in text_lines:
            m = EMAIL_RE.search(t)
            if m:
                return m.group(0)
        return None

    def _choose_website(self, text_lines: List[str]) -> Optional[str]:
        for t in text_lines:
            m = WWW_RE.search(t)
            if m:
                url = m.group(1)
                if not url.lower().startswith("http"):
                    url = "http://" + url
                return url
        return None

    def _choose_address(self, text_lines: List[str]) -> Optional[str]:
        address_lines = []
        for t in text_lines:
            low = t.lower()
            if any(k in low for k in STREET_KEYWORDS) or re.search(r'\d{3,}', t):
                address_lines.append(t)
        if not address_lines:
            # fallback: use last 2-3 non-empty lines
            tail = [t for t in text_lines if t and t.lower() not in ('email', 'phone')]
            if tail:
                return ", ".join(tail[-2:])
            return None
        return ", ".join(address_lines)

    def _choose_name_designation(self, text_lines: List[str]) -> (Optional[str], Optional[str]):
        for i, t in enumerate(text_lines):
            if t.strip():
                name = t.strip()
                designation = None
                if i + 1 < len(text_lines):
                    next_line = text_lines[i + 1].strip()
                    if next_line and len(next_line) < 60 and not EMAIL_RE.search(next_line) and not PHONE_RE.search(next_line):
                        designation = next_line
                return (name, designation)
        return (None, None)

    def extract(self, lines: List[Dict[str, Any]]) -> Dict[str, Any]:
        text_lines = [ln.get("text") for ln in lines if ln.get("text")]
        name, designation = self._choose_name_designation(text_lines)
        email = self._choose_email(text_lines)
        website = self._choose_website(text_lines)
        phone = self._choose_phone(text_lines)
        address = self._choose_address(text_lines)
        confidences = [ln.get("conf") for ln in lines if ln.get("conf") is not None]
        avg_conf = None
        if confidences:
            try:
                avg_conf = float(sum(confidences) / len(confidences))
            except Exception:
                avg_conf = None
        out = {
            "name": name,
            "designation": designation,
            "company": None,
            "email": email,
            "mobile": phone,
            "website": website,
            "address": address,
            "lines": text_lines,
            "confidence": avg_conf if avg_conf is not None else 0.0,
        }
        return out

    def recognize(self, image_bytes: Any, lang: str = "eng") -> Dict[str, Any]:
        pil_img = self._to_pil(image_bytes)
        osd_rot = None
        if get_osd_rotation is not None:
            try:
                osd_rot = get_osd_rotation(pil_img)
            except Exception:
                osd_rot = None
        else:
            try:
                osd_txt = pytesseract.image_to_osd(pil_img)
                m = re.search(r'Rotate:\s+(\d+)', osd_txt)
                if m:
                    osd_rot = int(m.group(1))
            except Exception:
                osd_rot = None

        tsv_data = self._run_tsv(pil_img, lang=lang)
        lines_grouped = self._group_words_to_lines(tsv_data)
        extracted = self.extract(lines_grouped)

        final_out = {
            "language_detected": lang,
            "osd_rotation": osd_rot if osd_rot is not None else 0,
            "name": extracted.get("name"),
            "designation": extracted.get("designation"),
            "company": extracted.get("company"),
            "email": extracted.get("email"),
            "mobile": extracted.get("mobile"),
            "website": extracted.get("website"),
            "address": extracted.get("address"),
            "lines": extracted.get("lines", []),
            "confidence": round(float(extracted.get("confidence") or 0.0), 2)
        }
        return final_out
