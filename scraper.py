import os
import time
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

# Configuration
BASE_URL = "https://issues.apache.org/jira/rest/api/2/search"
PROJECTS = ["KAFKA", "ZOOKEEPER", "CASSANDRA"] # 3 Apache Projects
RESULTS_PER_PAGE = 50
MAX_RESULTS_PER_PROJECT = 200  # Limit to avoid fetching millions of issues for this demo
DATA_DIR = "data"

# Setup resilient session with Retries
def get_session():
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1, # Wait 1s, 2s, 4s, etc.
        status_forcelist=[429, 500, 502, 503, 504], # Retry on these errors
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def save_page(project, page_num, data):
    """Saves a raw page of JSON data to disk."""
    filename = os.path.join(DATA_DIR, f"{project}_page_{page_num}.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_page_scraped(project, page_num):
    """Checks if we already have this page (Resumption Logic)."""
    filename = os.path.join(DATA_DIR, f"{project}_page_{page_num}.json")
    return os.path.exists(filename)

def scrape_project(session, project_key):
    print(f"--- Starting Scrape for {project_key} ---")
    
    # JQL (Jira Query Language) to get issues
    jql = f'project = {project_key} ORDER BY created DESC'
    
    start_at = 0
    page_num = 0
    
    # Progress bar
    pbar = tqdm(total=MAX_RESULTS_PER_PROJECT, desc=f"Fetching {project_key}")

    while start_at < MAX_RESULTS_PER_PROJECT:
        # 1. Check for Resumption
        if is_page_scraped(project_key, page_num):
            # print(f"Page {page_num} already exists. Skipping...")
            start_at += RESULTS_PER_PAGE
            page_num += 1
            pbar.update(RESULTS_PER_PAGE)
            continue

        # 2. Fetch Data
        try:
            params = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": RESULTS_PER_PAGE,
                "fields": "summary,description,status,priority,assignee,created,labels,comment"
            }
            response = session.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # If no more issues, break
            issues = data.get("issues", [])
            if not issues:
                break

            # 3. Save Data
            save_page(project_key, page_num, issues)
            
            # Update counters
            start_at += len(issues)
            page_num += 1
            pbar.update(len(issues))
            
            # 4. Rate Limiting (Politeness)
            time.sleep(0.5) 

        except Exception as e:
            print(f"\n[!] Error fetching {project_key} at index {start_at}: {e}")
            # In a real scenario, you might wait longer or break here. 
            # Thanks to 'Retry' adapter, transient network errors are already handled.
            break
            
    pbar.close()

def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    session = get_session()
    
    for project in PROJECTS:
        scrape_project(session, project)
        
    print("\nSuccess! Raw data collected in 'data/' directory.")

if __name__ == "__main__":
    main()