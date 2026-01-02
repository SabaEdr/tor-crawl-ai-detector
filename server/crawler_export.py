import os, time, re, json, csv, hashlib
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

def load_urls(path="urls.txt"):
    with open(path, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip() and not x.strip().startswith("#")]

def safe_id(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]

def main():
    os.makedirs("pages", exist_ok=True)
    out_csv = "crawl_export.csv"
    fieldnames = ["url", "status", "text_len", "text_file", "snippet", "error"]

    rows = []
    for url in load_urls():
        row = {k: "" for k in fieldnames}
        row["url"] = url

        try:
            html = fetch_html(url)
            text = html_to_text(html)
            fid = safe_id(url)
            text_path = os.path.join("pages", f"{fid}.txt")

            with open(text_path, "w", encoding="utf-8") as f:
                f.write(text)

            row["status"] = "ok"
            row["text_len"] = str(len(text))
            row["text_file"] = text_path
            row["snippet"] = text[:300]

        except Exception as e:
            row["status"] = "error"
            row["error"] = str(e)

        rows.append(row)
        time.sleep(3.0)

    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Saved: {out_csv} and pages/*.txt")

if __name__ == "__main__":
    main()
