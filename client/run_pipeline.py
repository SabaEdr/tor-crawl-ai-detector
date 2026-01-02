import os
import csv
import json
import tarfile
import time
import re
from datetime import datetime
from pathlib import Path

import paramiko
import requests

# -------------------------
# CONFIG
# -------------------------
SERVER_HOST = os.environ.get("CRAWL_SSH_HOST", "YOUR_SERVER_IP")
SERVER_PORT = int(os.environ.get("CRAWL_SSH_PORT", "22"))
SERVER_USER = os.environ.get("CRAWL_SSH_USER", "root")
SERVER_PASS = os.environ.get("CRAWL_SSH_PASS", "")

SSH_KEY_PATH = os.environ.get("CRAWL_SSH_KEY", "")

REMOTE_PROJECT_DIR = os.environ.get("REMOTE_PROJECT_DIR", "/root/tor_crawler")
REMOTE_VENV_ACTIVATE = os.environ.get("REMOTE_VENV_ACTIVATE", ".venv/bin/activate")
REMOTE_CRAWLER = os.environ.get("REMOTE_CRAWLER", "crawler_export.py")
REMOTE_BUNDLE = os.environ.get("REMOTE_BUNDLE", "crawl_bundle.tar.gz")

LOCAL_RUN_DIR = Path(os.environ.get("LOCAL_RUN_DIR", "run_output"))
LM_BASE = os.environ.get("LM_BASE_URL", "http://localhost:1234/v1")
LM_MODEL = os.environ.get("LM_MODEL", "")

# -------------------------
# LM Studio detector
# -------------------------
# مدل فقط label+reason بده؛ confidence را ما حساب می‌کنیم.
SYSTEM = (
    "You are performing authorship classification (AI vs human) on web page text. "
    "Use ONLY observable signals in the text. Do NOT guess based on topic.\n\n"
    "Decide label:\n"
    "- AI: strongly templated, overly generic, repetitive, unnatural transitions, excessive disclaimers, or LLM-like tone.\n"
    "- HUMAN: specific facts with natural imperfections, personal voice, irregular style, or clear human editorial cues.\n"
    "- UNKNOWN: too short, mostly boilerplate/navigation, or insufficient evidence.\n\n"
    "Return ONLY valid JSON (no markdown, no extra text): "
    "{\"label\":\"AI|HUMAN|UNKNOWN\",\"reason\":\"<=20 words\"}."
)


def lm_get_default_model():
    r = requests.get(f"{LM_BASE}/models", timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["data"][0]["id"]

def extract_json(s: str):
    s = s.strip()
    # remove code fences if present
    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)

    # try direct parse
    try:
        return json.loads(s)
    except Exception:
        pass

    # try to find first {...} block
    m = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None

def lm_classify(text: str, model_id: str) -> dict:
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Respond with JSON only.\n\nTEXT:\n" + text},
        ],
        "temperature": 0,
    }
    r = requests.post(f"{LM_BASE}/chat/completions", json=payload, timeout=120)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"].strip()

    obj = extract_json(content)
    if obj is None:
        return {"label": "UNKNOWN", "reason": "Could not parse JSON", "raw": content}

    label = str(obj.get("label", "UNKNOWN")).upper()
    reason = str(obj.get("reason", "")).strip()[:200]
    if label not in ("AI", "HUMAN", "UNKNOWN"):
        label = "UNKNOWN"

    return {"label": label, "reason": reason, "raw": content}

def make_chunks(text: str, max_chars=2500):
    text = text.strip()
    if len(text) <= max_chars:
        return [text]
    mid = len(text) // 2
    return [
        text[:max_chars],
        text[max(0, mid - max_chars//2): mid + max_chars//2],
        text[-max_chars:],
    ]

def aggregate_votes(preds):
    """
    preds: list of {"label":..., "reason":...}
    confidence = max(votes)/N  (قابل دفاع و غیرکالیبره، ولی منطقی)
    """
    if not preds:
        return ("UNKNOWN", 0.0, "no predictions")

    ai_votes = sum(1 for p in preds if p["label"] == "AI")
    human_votes = sum(1 for p in preds if p["label"] == "HUMAN")
    unk_votes = sum(1 for p in preds if p["label"] == "UNKNOWN")
    n = len(preds)

    if ai_votes > human_votes:
        verdict = "AI"
        top = ai_votes
    elif human_votes > ai_votes:
        verdict = "HUMAN"
        top = human_votes
    else:
        verdict = "UNKNOWN"
        top = max(ai_votes, human_votes, unk_votes)

    conf = top / n if n else 0.0
    votes_str = f"AI={ai_votes},HUMAN={human_votes},UNKNOWN={unk_votes}"
    return verdict, conf, votes_str

# -------------------------
# SSH helpers
# -------------------------
def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    if SSH_KEY_PATH:
        key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
        client.connect(SERVER_HOST, port=SERVER_PORT, username=SERVER_USER, pkey=key, timeout=20)
    else:
        if not SERVER_PASS:
            raise RuntimeError("Set CRAWL_SSH_PASS or CRAWL_SSH_KEY")
        client.connect(SERVER_HOST, port=SERVER_PORT, username=SERVER_USER, password=SERVER_PASS, timeout=20)

    return client

def ssh_run(client, command: str):
    stdin, stdout, stderr = client.exec_command(command, get_pty=True)
    out = stdout.read().decode("utf-8", errors="ignore")
    err = stderr.read().decode("utf-8", errors="ignore")
    code = stdout.channel.recv_exit_status()
    return code, out, err

# -------------------------
# CSV helpers
# -------------------------
def read_csv(path: Path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(path: Path, fieldnames, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

# -------------------------
# main pipeline
# -------------------------
def main():
    LOCAL_RUN_DIR.mkdir(parents=True, exist_ok=True)

    # 0) LM Studio up?
    try:
        model_id = LM_MODEL or lm_get_default_model()
    except Exception as e:
        raise RuntimeError(f"LM Studio API not reachable at {LM_BASE}. Start server in LM Studio. Details: {e}")

    print("LM model:", model_id)

    # 1) SSH to server, run crawler, make bundle
    client = ssh_connect()
    try:
        remote_cmd = (
            f"cd {REMOTE_PROJECT_DIR} && "
            f"source {REMOTE_VENV_ACTIVATE} && "
            f"python {REMOTE_CRAWLER} && "
            f"tar -czf {REMOTE_BUNDLE} crawl_export.csv pages/ && "
            f"ls -lh {REMOTE_BUNDLE}"
        )
        print("Running remote crawl...")
        code, out, err = ssh_run(client, remote_cmd)
        print(out.strip())
        if code != 0:
            raise RuntimeError(f"Remote command failed (code={code}):\n{err}\n{out}")

        # 2) Download bundle via SFTP
        local_bundle = LOCAL_RUN_DIR / "crawl_bundle.tar.gz"
        remote_bundle_path = f"{REMOTE_PROJECT_DIR}/{REMOTE_BUNDLE}"
        print("Downloading bundle...")
        sftp = client.open_sftp()
        sftp.get(remote_bundle_path, str(local_bundle))
        sftp.close()
        print("Saved:", local_bundle)

    finally:
        client.close()

    # 3) Extract bundle
    print("Extracting...")
    with tarfile.open(local_bundle, "r:gz") as tf:
        tf.extractall(path=LOCAL_RUN_DIR)

    pages_dir = LOCAL_RUN_DIR / "pages"
    crawl_csv = LOCAL_RUN_DIR / "crawl_export.csv"
    if not pages_dir.exists() or not crawl_csv.exists():
        raise RuntimeError("Bundle missing pages/ or crawl_export.csv")

    # 4) AI detect
    ai_rows = []
    for txt in sorted(pages_dir.glob("*.txt")):
        text = txt.read_text(encoding="utf-8", errors="ignore").strip()
        if not text:
            continue

        chunks = make_chunks(text, 2500)
        preds = [lm_classify(c, model_id) for c in chunks]

        verdict, conf, votes = aggregate_votes(preds)
        reason = " | ".join(p.get("reason", "") for p in preds)[:200]

        ai_rows.append({
            "text_file": str(Path("pages") / txt.name),
            "label": verdict,
            "confidence": f"{conf:.3f}",
            "votes": votes,
            "reason": reason,
        })

        print(f"{txt.name}: {verdict} (conf={conf:.2f}, {votes})")
        time.sleep(0.15)

    ai_csv = LOCAL_RUN_DIR / "ai_report.csv"
    write_csv(ai_csv, ["text_file", "label", "confidence", "votes", "reason"], ai_rows)
    print("Saved:", ai_csv)

    # 5) Merge to final report
    crawl_rows = read_csv(crawl_csv)
    ai_map = {r["text_file"].replace("\\", "/"): r for r in ai_rows}

    final = []
    for r in crawl_rows:
        tf = (r.get("text_file") or "").replace("\\", "/")
        hit = ai_map.get(tf) or ai_map.get(str(Path(tf)))
        final.append({
            "url": r.get("url", ""),
            "status": r.get("status", ""),
            "text_len": r.get("text_len", ""),
            "text_file": tf,
            "ai_label": (hit or {}).get("label", ""),
            "ai_confidence": (hit or {}).get("confidence", ""),
            "ai_votes": (hit or {}).get("votes", ""),
            "ai_reason": (hit or {}).get("reason", ""),
            "error": r.get("error", ""),
        })

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final_csv = LOCAL_RUN_DIR / f"final_report_{stamp}.csv"
    write_csv(final_csv,
              ["url","status","text_len","text_file","ai_label","ai_confidence","ai_votes","ai_reason","error"],
              final)
    print("Saved:", final_csv)

if __name__ == "__main__":
    main()
