import os
import csv
import json
import time
from pathlib import Path
import requests

LM_BASE = os.environ.get("LM_BASE_URL", "http://localhost:1234/v1")
MODEL = os.environ.get("LM_MODEL", "")  # اگر خالی باشه از /models می‌گیریم

SYSTEM = (
    "You are a classifier. Decide if the given text is AI-generated or human-written. "
    "Return STRICT JSON only with keys: label (AI/HUMAN/UNKNOWN), confidence (0-1), reason (<=20 words)."
)

def get_default_model():
    r = requests.get(f"{LM_BASE}/models", timeout=10)
    r.raise_for_status()
    data = r.json()
    # LM Studio معمولاً data: [{id: "..."}]
    return data["data"][0]["id"]

def classify(text: str, model_id: str):
    prompt = (
        "Classify the following text. Output only JSON.\n\n"
        f"TEXT:\n{text}"
    )
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
    }
    r = requests.post(f"{LM_BASE}/chat/completions", json=payload, timeout=120)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()
    try:
        obj = json.loads(content)
        label = str(obj.get("label", "UNKNOWN")).upper()
        conf = float(obj.get("confidence", 0.0))
        reason = str(obj.get("reason", ""))[:200]
        if label not in ("AI", "HUMAN", "UNKNOWN"):
            label = "UNKNOWN"
        conf = max(0.0, min(1.0, conf))
        return {"label": label, "confidence": conf, "reason": reason, "raw": content}
    except Exception:
        return {"label": "UNKNOWN", "confidence": 0.0, "reason": "Could not parse JSON", "raw": content}

def main():
    pages = Path("pages")
    out_csv = "ai_report.csv"
    model_id = MODEL or get_default_model()
    print("Using model:", model_id)

    fieldnames = ["text_file", "text_len", "label", "confidence", "reason"]
    rows = []

    for p in sorted(pages.glob("*.txt")):
        text = p.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue

        # برای جلوگیری از کندی: فقط اولین 2500 کاراکتر (baseline)
        chunk = text[:2500]

        res = classify(chunk, model_id)
        rows.append({
            "text_file": str(p),
            "text_len": str(len(text)),
            "label": res["label"],
            "confidence": f"{res['confidence']:.3f}",
            "reason": res["reason"],
        })

        time.sleep(0.2)  # نرخ درخواست

        print(f"{p.name}: {res['label']} ({res['confidence']:.2f})")

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print("\nSaved:", out_csv)

if __name__ == "__main__":
    main()
