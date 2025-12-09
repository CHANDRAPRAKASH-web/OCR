from . import tesseract_driver as driver

class Recognize:
    def _init_(self):
        pass

    def extract(self, image_bytes, lang="eng"):
        try:
            osd_rotation = driver.get_osd_rotation(image_bytes)
        except Exception:
            osd_rotation = 0
        data = driver.run_tesseract_data(image_bytes, lang=lang)
        lines = data.get("text", [])
        raw = data.get("raw", {})
        joined_text = "\n".join(lines)
        result = {
            "language_detected": lang,
            "osd_rotation": osd_rotation,
            "lines": lines,
            "text": joined_text,
            "raw": raw
        }
        return result
