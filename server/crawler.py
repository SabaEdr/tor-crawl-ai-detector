import time, re, csv
import requests
from bs4 import BeautifulSoup
from readability import Document

TOR = "socks5h://127.0.0.1:9050"

def fetch_html(url: str, timeout=45) -> str:
    s = requests.Session()
    s.proxies = {"http": TOR, "https": TOR}
    s.headers.update({"User-Agent": "ResearchCrawler/1.0"})
    r = s.get(url, timeout=timeout, allow_redirects=True)
    r.raise_for_status()
    ctype = (r.headers.get("Content-Type") or "").lower()
    if "text/html" not in ctype and "application/xhtml" not in ctype:
        raise ValueError(f"Non-HTML content-type: {ctype}")
    return r.text

def html_to_text(html: str) -> str:
    doc = Document(html)
    main_html = doc.summary()
    soup = BeautifulSoup(main_html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()

def chunk_text(text: str, max_chars=2500, max_chunks=4):
    if not text:
        return []
    chunks = [text[i:i+max_chars] for i in range(0, len(text), max_chars)]
    return chunks[:max_chunks]

def load_urls(path="urls.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip() and not x.strip().startswith("#")]

def main():
    out_path = "crawl_report.csv"
    fieldnames = ["url", "status", "text_len", "snippet", "error"]

    rows = []
    for url in load_urls():
        row = {"url": url, "status": "", "text_len": "", "snippet": "", "error": ""}
        try:
            html = fetch_html(url)
            text = html_to_text(html)
            row["status"] = "ok"
            row["text_len"] = str(len(text))
            row["snippet"] = text[:300]
        except Exception as e:
            row["status"] = "error"
            row["error"] = str(e)

        rows.append(row)
        time.sleep(3.0)  # rate limit

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # چاپ خلاصه
    for r in rows:
        print(f"{r['status']:5}  len={r['text_len'] or '-':>6}  {r['url']}")
    print(f"\nSaved: {out_path}")

if __name__ == "__main__":
    main()

