import pytesseract
import pandas as pd
import io

def run_tesseract_data(image_bytes, lang="eng", psm=6, oem=1):
    img = Image.open(io.BytesIO(image_bytes))
    # config: OEM 1 (LSTM), PSM choose 6/3/4 depending on card layout
    config = f'--oem {oem} --psm {psm} -c tessedit_char_whitelist=0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ@.-,:/\\#'
    # request TSV
    tsv = pytesseract.image_to_data(img, lang=lang, config=config, output_type=pytesseract.Output.DATAFRAME)
    # clean and aggregate by line_num
    if isinstance(tsv, pd.DataFrame) and not tsv.empty:
        # group by line
        lines = []
        confs = []
        for line_no, g in tsv.groupby(['block_num','par_num','line_num'], sort=False):
            text = " ".join([str(t).strip() for t in g['text'].tolist() if str(t).strip() != ''])
            conf_vals = [c for c in g['conf'].tolist() if isinstance(c, (int, float)) and c >= 0]
            mean_conf = float(np.mean(conf_vals)) if conf_vals else 0.0
            lines.append(text)
            confs.append(mean_conf)
        raw = {
            "tsv": tsv.to_dict(orient="list")
        }
        return {"text": lines, "conf": confs, "raw": raw}
    else:
        return {"text": [], "conf": [], "raw": {}}
