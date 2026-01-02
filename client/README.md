### LM Studio (Local) Setup — Client Side

This project runs **AI detection locally on your Windows machine** using **LM Studio** as an OpenAI-compatible API server. The crawler runs on the remote server; only the **analysis/detection** runs here.

---

## 1) Install LM Studio

1. Download and install **LM Studio** on Windows.
2. Open LM Studio.

---

## 2) Download / Load a Model

1. Go to **Models** tab.
2. Download a model you want to use (example: `qwen2.5-vl-7b-instruct` or any instruct model).
3. Make sure the model is **fully downloaded** and shows as available.

> Tip: If your detector is only text-based, you can also use a pure text instruct model (no vision needed).

---

## 3) Start the Local API Server (Important)

1. Go to **Developer** (or **Local Server**) section in LM Studio.
2. Enable **OpenAI-compatible API**.
3. Set a port (default is usually **1234**).
4. Click **Start Server**.

You should end up with something like:

* Base URL: `http://localhost:1234/v1`

---

## 4) Quick Health Checks

### Check models endpoint

Open in browser:

* `http://localhost:1234/v1/models`

Or in PowerShell:

```powershell
curl http://localhost:1234/v1/models
```

If LM Studio is running correctly, you should get JSON back.

---

## 5) Configure the Project to Use LM Studio

In PowerShell (same terminal where you run the pipeline), set these env vars:

```powershell
$env:LM_BASE_URL="http://localhost:1234/v1"
$env:LM_MODEL="qwen2.5-vl-7b-instruct"   # optional; if empty it auto-picks first model
```

If you don’t set `LM_MODEL`, the code will call `/models` and pick the first available one.

---

## 6) Run the Pipeline

Make sure your local Python venv is active, then run:

```powershell
python run_pipeline.py
```

Expected flow:

* Connects to server via SSH
* Runs crawler remotely
* Downloads `crawl_bundle.tar.gz`
* Extracts pages
* Sends extracted text to LM Studio API for AI detection
* Outputs `final_report.csv`

---

## Common Errors & Fixes

###  `LM Studio API not reachable at http://localhost:1234/v1`

**Fix:** Start the server inside LM Studio (Step 3) and re-check:

* `http://localhost:1234/v1/models`

###  `ConnectionRefusedError [WinError 10061]`

**Fix:** Same as above — the port is not listening. Either:

* server not started
* wrong port in `LM_BASE_URL`

###  “Could not parse JSON”

**Fix:** Your model sometimes replies with extra text. This usually improves by:

* using a stronger instruct model
* keeping temperature = 0 (already set)
* shortening input chunks

---

