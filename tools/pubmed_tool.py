import requests
import time

def search_pubmed(query, max_results=100, min_date="2025/01/01", max_date="2026/12/31", max_retries=3):
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    params = {
        "db": "pubmed",
        "term": f"{query} AND humans[MeSH Terms]",
        "retmax": max_results,
        "retmode": "json",
        "datetype": "pdat",
        "mindate": min_date,
        "maxdate": max_date,
        "sort": "relevance"
    }

    for attempt in range(max_retries):
        try:
            response = requests.get(search_url, params=params, timeout=10)
            response.raise_for_status()
            ids = response.json()["esearchresult"]["idlist"]
            break
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            print(f"PubMed search attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff: 1s, 2s, 4s
            else:
                print("PubMed search failed after all retries - returning empty results for this query.")
                return []

    if not ids:
        return []

    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}

    for attempt in range(max_retries):
        try:
            response = requests.get(summary_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()["result"]
            break
        except (requests.exceptions.RequestException, KeyError, ValueError) as e:
            print(f"PubMed summary attempt {attempt+1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return []

    articles = []
    for pid in ids:
        item = data[pid]
        articles.append({
            "title": item.get("title"),
            "pubdate": item.get("pubdate"),
            "journal": item.get("source"),
            "pmid": pid,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/"
        })
    return articles