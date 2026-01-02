# Tor-based Web Crawler & Local AI Content Detector

This project implements a **two-stage pipeline** for crawling web pages through the **Tor network** and analyzing their textual content using a **locally hosted large language model (LLM)**.
The system is intentionally split between a **remote server** and a **local machine** to ensure stability, privacy, and efficient resource usage.

---

## Project Overview

The main goal of this project is to:

* Collect web pages anonymously using the Tor network
* Extract and clean meaningful textual content from crawled pages
* Analyze the extracted text to estimate whether it is **AI-generated or human-written**

Due to network restrictions and Tor connectivity limitations on local machines (especially in restricted network environments), the crawling process is executed on a **remote server**, while AI-based analysis is performed **locally**.

---

## Architecture

The system is divided into two clearly separated components:

### 1. Remote Server (Crawling Layer)

Runs on a Linux server with stable access to the Tor network.

Responsibilities:

* Establish connection to the Tor network
* Crawl target URLs through Tor SOCKS proxy
* Extract main textual content from HTML pages
* Store extracted text as `.txt` files
* Export crawl metadata as CSV
* Package crawl results into a compressed archive

Technologies:

* Tor
* Python
* Requests (SOCKS)
* BeautifulSoup / Readability
* SSH (for remote execution)

---

### 2. Local Machine (Analysis Layer)

Runs on the user’s local system.

Responsibilities:

* Trigger crawling remotely via SSH
* Download crawl results from the server
* Run AI-based text analysis locally
* Detect AI-generated content using a local LLM
* Generate final merged reports

Technologies:

* Python
* LM Studio (OpenAI-compatible local API)
* Local LLM (e.g. Qwen, LLaMA-based models)
* Pandas / CSV processing

---

## Why Tor?
* Improve privacy and anonymity during crawling
* Avoid IP-based blocking and tracking
* Simulate realistic anonymous browsing behavior

**Important:**
This project uses Tor **only as a client**.
It does **not** operate as an exit relay, directory relay, or public proxy.

---

## Why Separate Server and Local Execution?

Running both Tor crawling and AI inference on a single machine introduces several problems:

* Tor bootstrap instability on restricted networks
* High CPU/RAM usage during local LLM inference
* Reduced crawl reliability

Separating these responsibilities results in:

* Stable Tor connectivity on the server
* Faster and safer AI inference locally
* Cleaner system design and easier debugging

---

## Workflow

1. Local machine connects to the remote server via SSH
2. Crawler is executed on the server through Tor
3. Crawl results are packaged (`CSV + text files`)
4. Results are downloaded to the local machine
5. Local LLM analyzes text chunks
6. Final report is generated with AI labels and confidence scores

---

## Output Files

* `crawl_export.csv`
  Metadata for each crawled URL (status, text length, file reference)

* `pages/*.txt`
  Cleaned textual content extracted from each page

* `ai_report.csv`
  AI detection results per text file

* `final_report.csv`
  Merged crawl + AI analysis report

---

## AI Detection Notes

* Uses a **general-purpose LLM**, not a specialized AI-detector model
* Decisions are based on stylistic and structural patterns
* Output labels:

  * `AI`
  * `HUMAN`
  * `UNKNOWN`
* Confidence scores are **heuristic**, not absolute guarantees

Results should be interpreted with caution, especially for:

* Formal or technical texts
* Short or low-context content

---

## Security & Ethical Considerations

* No brute-force, exploitation, or intrusive scanning is performed
* Crawling respects basic request limits and timeouts
* Tor usage is limited to outbound client traffic
* Intended strictly for **educational and research purposes**

---

