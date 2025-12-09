from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from ocr.recognition import Recognize
import traceback

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
        result = recognizer.extract(image_bytes, lang=lang)
        return JSONResponse(result)
    except Exception as e:
        return JSONResponse(
            {"error": "OCR pipeline error", "detail": str(e), "trace": traceback.format_exc()},
            status_code=500
        )
