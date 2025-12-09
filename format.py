import math
import json
from decimal import Decimal
import numpy as np
import traceback

def _is_non_finite_number(x):
    try:
        f = float(x)
        return not math.isfinite(f)
    except Exception:
        return False

def sanitize(obj, path="root"):
    # dict
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            out[k] = sanitize(v, f"{path}.{k}")
        return out
    # list / tuple
    if isinstance(obj, (list, tuple)):
        lst = [sanitize(v, f"{path}[{i}]") for i, v in enumerate(obj)]
        return lst if isinstance(obj, list) else tuple(lst)
    # numpy scalar
    if isinstance(obj, (np.generic, )):
        py = obj.item()
        if isinstance(py, (float, int)):
            if _is_non_finite_number(py):
                print(f"[sanitize] non-finite at {path}: {py}")
                return None
            return py
        return py
    # numpy array -> list
    if isinstance(obj, (np.ndarray, )):
        try:
            lst = obj.tolist()
            return sanitize(lst, path)
        except Exception:
            print(f"[sanitize] could not convert ndarray at {path}")
            return None
    # Decimal
    if isinstance(obj, Decimal):
        try:
            f = float(obj)
            if not math.isfinite(f):
                print(f"[sanitize] non-finite Decimal at {path}: {obj}")
                return None
            return f
        except Exception:
            return str(obj)
    # bytes / bytearray => decode or repr
    if isinstance(obj, (bytes, bytearray)):
        try:
            return obj.decode("utf-8")
        except Exception:
            return repr(obj)
    # complex -> not JSON, return str or None
    if isinstance(obj, complex):
        print(f"[sanitize] complex number at {path}: {obj}")
        return None
    # floats & ints
    if isinstance(obj, float):
        if not math.isfinite(obj):
            print(f"[sanitize] non-finite float at {path}: {obj}")
            return None
        return float(obj)
    if isinstance(obj, (int, bool)):
        return obj
    # strings
    if isinstance(obj, str):
        return obj
    # fallback: try json-serializable via conversion
    try:
        json.dumps(obj)
        return obj
    except Exception:
        # last resort: return str() but log
        try:
            s = str(obj)
            print(f"[sanitize] fallback str() at {path}: {s}")
            return s
        except Exception:
            print(f"[sanitize] cannot convert object at {path}, returning None")
            return None
