import os
import io
import re
import numpy as np
from PIL import Image
import pytesseract
from pytesseract import Output
import cv2

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\tesseract\tesseract.exe"

def ensure_rgb(img):
    if isinstance(img, Image.Image):
        pil_rgb = img.convert("RGB")
        arr = np.array(pil_rgb)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    if isinstance(img, (bytes, bytearray)):
        pil = Image.open(io.BytesIO(img)).convert("RGB")
        arr = np.array(pil)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    if isinstance(img, np.ndarray):
        if img.ndim == 2:
            return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        if img.shape[2] == 4:
            try:
                rgb = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            except Exception:
                return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
    try:
        pil = Image.open(io.BytesIO(img)).convert("RGB")
        arr = np.array(pil)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except Exception as e:
        raise ValueError("Unsupported image input to ensure_rgb") from e

def get_osd_rotation(img):
    try:
        if isinstance(img, (bytes, bytearray)):
            pil = Image.open(io.BytesIO(img))
        elif isinstance(img, np.ndarray):
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        else:
            pil = img
        osd = pytesseract.image_to_osd(pil)
        m = re.search(r'Rotate:\s+(\d+)', osd)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0

def run_tesseract_data(img, lang="eng"):
    try:
        if isinstance(img, (bytes, bytearray)):
            pil = Image.open(io.BytesIO(img)).convert("RGB")
        elif isinstance(img, np.ndarray):
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        else:
            pil = img.convert("RGB")
        data = pytesseract.image_to_data(pil, output_type=Output.DICT, lang=lang)
        text_lines = []
        # Reconstruct simple text lines from the data output
        n = len(data.get("text", []))
        current_line = []
        last_block_num = -1
        for i in range(n):
            word = data["text"][i].strip()
            if not word:
                continue
            block = (data.get("block_num", [None]*n))[i]
            line_num = (data.get("line_num", [None]*n))[i]
            if (block, line_num) != (last_block_num, data.get("line_num", [None]*n)[i]):
                if current_line:
                    text_lines.append(" ".join(current_line))
                current_line = [word]
                last_block_num = block
            else:
                current_line.append(word)
        if current_line:
            text_lines.append(" ".join(current_line))
        return {"text": text_lines, "raw": data}
    except Exception as e:
        raise
