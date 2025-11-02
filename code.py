#!/usr/bin/env python3
# collect_admin_pipeline.py
# Pipeline complet : scraping sites burkinabè, téléchargement PDF, extraction texte, nettoyage,
# normalisation, dé-duplication, et export data/corpus.json + data/sources.txt
# Respecte robots.txt, temporisation, et stockage raw.

import os, time, json, hashlib, re, logging
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from pdfminer.high_level import extract_text as extract_pdf_text
from urllib import robotparser
from tqdm import tqdm

# ---------- CONFIG ----------
BASE_DATA_DIR = r"C:\Users\HP\OneDrive\Documents\SN"
DATA_DIR = os.path.join(BASE_DATA_DIR, "data_admin")
RAW_HTML_DIR = os.path.join(DATA_DIR, "raw_html")
PDF_DIR = os.path.join(DATA_DIR, "pdfs")
MANUAL_DIR = os.path.join(DATA_DIR, "manual")
LOG_FILE = os.path.join(DATA_DIR, "scrape.log")
SOURCES_TXT = os.path.join(DATA_DIR, "sources.txt")
CORPUS_JSON = os.path.join(DATA_DIR, "corpus.json")

# Créer les dossiers si inexistants
os.makedirs(RAW_HTML_DIR, exist_ok=True)
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(MANUAL_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Seeds
SEED_SITES = [
    "https://servicepublic.gov.bf/",
    "https://www.matd.gov.bf/",
    "https://www.justice.gov.bf/",
    "https://www.dgi.gov.bf/",
    "https://www.cnss.bf/",
    "https://oni.bf/",
    "https://www.finances.gov.bf/",
    "https://www.jobf.gov.bf/",
    "https://www.ambassadeburkina.fr/",
    "https://lefaso.net/",
    "https://burkina24.com/"
]

USER_AGENT = "Mozilla/5.0 (compatible; ResourceCollector/1.0; +https://example.org)"
REQUESTS_TIMEOUT = 12
SLEEP_BETWEEN_REQUESTS = 0.8
TARGET_COUNT = 500

# Logging
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)

# ---------- UTIL ----------
session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})

def safe_get(url):
    try:
        r = session.get(url, timeout=REQUESTS_TIMEOUT)
        r.raise_for_status()
        return r
    except Exception as e:
        logging.warning(f"GET failed {url}: {e}")
        return None

def obeys_robots(url):
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = robotparser.RobotFileParser()
    rp.set_url(urljoin(base, "/robots.txt"))
    try:
        rp.read()
    except:
        return True
    return rp.can_fetch(USER_AGENT, url)

def normalize_text(s, max_len=5000):
    if not s:
        return ""
    # Supprimer les caractères non imprimables
    s = re.sub(r'[\x00-\x1F\x7F-\x9F]', ' ', s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        return s[:max_len] + " …"
    return s

def sha256_of_bytes(b):
    return hashlib.sha256(b).hexdigest()

# ---------- SCRAPING ----------
def extract_links_from_page(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a['href'].strip()
        if href.startswith("#") or href.lower().startswith("mailto:"):
            continue
        full = urljoin(base_url, href) if not href.startswith("http") else href
        links.add(full.split("#")[0])
    return links

def extract_main_text(html):
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        {"name":"article"},
        {"name":"div", "class_":"texte"},
        {"name":"div", "class_":"entry-content"},
        {"name":"div", "class_":"post-content"},
        {"name":"div", "class_":"content"},
        {"name":"main"}
    ]
    for sel in selectors:
        node = soup.find(**sel)
        if node:
            text = node.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text
    body = soup.body.get_text(separator="\n", strip=True) if soup.body else soup.get_text(separator="\n", strip=True)
    return body[:5000]

def save_raw_html(url, html):
    fname = hashlib.sha1(url.encode('utf-8')).hexdigest() + ".html"
    path = os.path.join(RAW_HTML_DIR, fname)
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def download_pdf(url):
    r = safe_get(url)
    if not r:
        return None
    content = r.content
    h = sha256_of_bytes(content)
    fname = h + "_" + os.path.basename(urlparse(url).path)
    path = os.path.join(PDF_DIR, fname)
    with open(path, "wb") as f:
        f.write(content)
    return path

# ---------- MAIN CRAWLER ----------
def crawl(seeds, target=TARGET_COUNT, max_pages=3000):
    to_visit = seeds.copy()
    visited = set()
    corpus = []
    sources = []

    pbar = tqdm(total=target, desc="Collected")
    while to_visit and len(corpus) < target:
        url = to_visit.pop(0)
        if url in visited: continue
        visited.add(url)

        if not url.lower().startswith(("http://","https://")): continue
        if not obeys_robots(url): 
            logging.info(f"Robots disallow: {url}")
            continue

        r = safe_get(url)
        if not r: continue

        content_type = r.headers.get("Content-Type","").lower()
        # PDF
        if "application/pdf" in content_type or url.lower().endswith(".pdf"):
            pdf_path = download_pdf(url)
            if pdf_path:
                try:
                    txt = extract_pdf_text(pdf_path, maxpages=0)
                except:
                    txt = "[PDF non convertible en texte]"
                entry = {
                    "id": hashlib.sha1(url.encode()).hexdigest(),
                    "title": os.path.basename(pdf_path),
                    "category": "pdf",
                    "source": url,
                    "source_file": pdf_path,
                    "content": normalize_text(txt)
                }
                corpus.append(entry)
                sources.append(url)
                pbar.update(1)
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            continue

        # HTML
        html = r.text
        raw_path = save_raw_html(url, html)
        main_text = extract_main_text(html)
        try:
            soup = BeautifulSoup(html, "html.parser")
            h1 = soup.find("h1")
            title = h1.get_text(strip=True) if h1 else (soup.title.get_text(strip=True) if soup.title else url)
        except:
            title = url

        if len(main_text) < 200:
            logging.info(f"Skipped (too small): {url}")
        else:
            entry = {
                "id": hashlib.sha1(url.encode()).hexdigest(),
                "title": normalize_text(title, max_len=300),
                "category": "webpage",
                "source": url,
                "raw_html": raw_path,
                "content": normalize_text(main_text)
            }
            corpus.append(entry)
            sources.append(url)
            pbar.update(1)

        # enqueue links
        try:
            links = extract_links_from_page(html, url)
            for l in links:
                parsed_seed = urlparse(url).netloc
                if parsed_seed in l or any(d in l for d in [".gov.bf", "servicepublic.gov.bf", "jobf.gov.bf", "lefaso.net", "burkina24.com"]):
                    if l not in visited and l not in to_visit:
                        to_visit.append(l)
        except Exception as e:
            logging.warning(f"Link extraction failed {url}: {e}")

        time.sleep(SLEEP_BETWEEN_REQUESTS)
        if len(visited) > max_pages:
            logging.info("Max pages visited reached, stopping crawl.")
            break

    pbar.close()
    return corpus, sources

# ---------- DEDUPLICATION ----------
def dedupe_corpus(corpus):
    seen = set()
    out = []
    for e in corpus:
        key = (e.get("title",""), e.get("content","")[:200])
        h = hashlib.sha1("||".join(key).encode("utf-8")).hexdigest()
        if h in seen:
            continue
        seen.add(h)
        out.append(e)
    return out

# ---------- SAVE ----------
def save_outputs(corpus, sources):
    corpus = dedupe_corpus(corpus)
    with open(CORPUS_JSON, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)
    with open(SOURCES_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(sources))
    logging.info(f"Saved corpus: {len(corpus)} entries. sources: {len(sources)}")

# ---------- RUN ----------
if __name__ == "__main__":
    logging.info("Starting crawl...")
    corpus, sources = crawl(SEED_SITES, target=TARGET_COUNT, max_pages=4000)
    save_outputs(corpus, sources)

    # Rapport automatique
    num_html = sum(1 for e in corpus if e['category'] == 'webpage')
    num_pdf = sum(1 for e in corpus if e['category'] == 'pdf')
    total_entries = len(corpus)
    logging.info("----- RAPPORT DE COLLECTE -----")
    logging.info(f"Total documents collectés : {total_entries}")
    logging.info(f"Pages HTML sauvegardées : {num_html}")
    logging.info(f"PDF sauvegardés : {num_pdf}")
    logging.info(f"Sources totales listées : {len(sources)}")
    logging.info("--------------------------------")
    print(f"Rapport terminé : {total_entries} documents (HTML={num_html}, PDF={num_pdf})")
