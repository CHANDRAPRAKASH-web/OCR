from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from ocr.recognition import Recognize
import traceback
import math
import numpy as np
import pandas as pd
from decimal import Decimal

def _is_non_finite_val(v):
    try:
        if pd.isna(v):
            return True
    except Exception:
        pass
    if isinstance(v, np.generic):
        try:
            v = v.item()
        except Exception:
            pass
    try:
        fv = float(v)
        if not math.isfinite(fv):
            return True
    except Exception:
        pass
    return False

def sanitize(obj):
    try:
        if _is_non_finite_val(obj):
            return None
    except Exception:
        pass
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize(v) for v in obj]
    if isinstance(obj, np.ndarray):
        try:
            return sanitize(obj.tolist())
        except Exception:
            return None
    if isinstance(obj, np.generic):
        try:
            return sanitize(obj.item())
        except Exception:
            return None
    try:
        if isinstance(obj, (pd.Timestamp, pd.Timedelta)):
            return str(obj)
    except Exception:
        pass
    if isinstance(obj, Decimal):
        try:
            f = float(obj)
            return None if not math.isfinite(f) else f
        except Exception:
            return str(obj)
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8", "replace")
        except Exception:
            return repr(obj)
    if isinstance(obj, complex):
        return None
    if isinstance(obj, (float, int, bool, str)):
        return obj
    try:
        return str(obj)
    except Exception:
        return None

app = FastAPI(title="Visiting Card OCR API")

recognizer = Recognize()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract(file: UploadFile = File(...), lang: str = Form("eng")):
    try:
        image_bytes = await file.read()
        if not image_bytes:
            return JSONResponse({"detail": "provide file"}, status_code=400)
        # call recognizer and sanitize output
        result = recognizer.recognize(image_bytes, lang=lang)
        safe = sanitize(result)
        return JSONResponse(content=safe)
    except Exception as e:
        return JSONResponse(
            {"error": "OCR pipeline error", "detail": str(e), "trace": traceback.format_exc()},
            status_code=500
        )
