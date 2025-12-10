from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from ocr.recognition import Recognize
import traceback
import math
import json
from decimal import Decimal
import numpy as np
import pandas as pd

def _is_non_finite_val(v):
    try:
        # pandas.isna handles pd.NA, NaT and numpy NaN nicely
        if pd.isna(v):
            return True
    except Exception:
        pass
    # numpy scalar
    if isinstance(v, np.generic):
        try:
            v = v.item()
        except Exception:
            pass
    # floats / decimals / inf/nan
    try:
        fv = float(v)
        if not math.isfinite(fv):
            return True
    except Exception:
        pass
    return False

def sanitize(obj):
    # missing / NaN / NA / Inf -> None
    try:
        if _is_non_finite_val(obj):
            return None
    except Exception:
        pass

    # dict
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}

    # list/tuple
    if isinstance(obj, (list, tuple, set)):
        return [sanitize(v) for v in obj]

    # numpy array -> list
    if isinstance(obj, np.ndarray):
        try:
            return sanitize(obj.tolist())
        except Exception:
            return None

    # numpy scalar
    if isinstance(obj, np.generic):
        try:
            return sanitize(obj.item())
        except Exception:
            return None

    # pandas types
    try:
        if isinstance(obj, (pd.Timestamp, pd.Timedelta)):
            return str(obj)
    except Exception:
        pass

    # Decimal
    if isinstance(obj, Decimal):
        try:
            f = float(obj)
            return None if not math.isfinite(f) else f
        except Exception:
            return str(obj)

    # bytes
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8", "replace")
        except Exception:
            return repr(obj)

    # complex -> not JSON serializable, drop it
    if isinstance(obj, complex):
        return None

    # floats/ints/bools/str
    if isinstance(obj, (float, int, bool, str)):
        # float already checked above for non-finite
        return obj

    # fallback: try to convert to python scalar
    try:
        return obj._dict_ if hasattr(obj, "_dict_") else str(obj)
    except Exception:
        return None

app = FastAPI(title="Visiting Card OCR API")

recognizer = Recognize()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/extract")
async def extract(file: UploadFile = File(...), lang: str = Form("eng")):
    print("=== OCR PIPELINE START ===")
    try:
        image_bytes = await file.read()
        if not image_bytes:
            return JSONResponse({"detail": "provide file"}, status_code=400)
        result= recognizer.recognize(image_bytes, lang=lang)
        safe= sanitize(result)
        return JSONResponse(content= safe)
    except Exception as e:
        return JSONResponse(
            {"error": "OCR pipeline error", "detail": str(e), "trace": traceback.format_exc()},
            status_code=500
        )
