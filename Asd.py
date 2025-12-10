# inside extract(...) route where you call recognizer.recognize
try:
    image_bytes = await file.read()
    if not image_bytes:
        return JSONResponse({"detail": "provide file"}, status_code=400)

    # call recognizer
    result = recognizer.recognize(image_bytes, lang=lang)

    # debug helpful output to server console (remove later)
    print("DEBUG: raw recognizer result type:", type(result))
    # if recognizer returned None or empty -> return an error so we don't send null
    if result is None:
        return JSONResponse({"error": "OCR returned no result (None)."}, status_code=500)
    if not isinstance(result, dict):
        # return debugging payload so we can inspect what it returned
        return JSONResponse({"error": "OCR returned unexpected type", "type": str(type(result)), "value": str(result)}, status_code=500)

    safe = sanitize(result)
    return JSONResponse(content=safe)
except Exception as e:
    return JSONResponse(
        {"error": "OCR pipeline error", "detail": str(e), "trace": traceback.format_exc()},
        status_code=500
    )
