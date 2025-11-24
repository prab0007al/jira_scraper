import os
import time
import json
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://issues.apache.org/jira/rest/api/2/search"
PROJECTS = ["KAFKA", "ZOOKEEPER", "CASSANDRA"]  # 3 Apache Projects
RESULTS_PER_PAGE = 50
MAX_RESULTS_PER_PROJECT = 200  # Limit to avoid fetching millions of issues
DATA_DIR = "data"

# Setup resilient session with Retries
def get_session():
    """Create a requests session with retry logic for resilience."""
    session = requests.Session()
    retry = Retry(
        total=5,
        backoff_factor=1,  # Wait 1s, 2s, 4s, 8s, 16s
        status_forcelist=[429, 500, 502, 503, 504],  # Retry on these errors
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def save_page(project, page_num, data):
    """Saves a raw page of JSON data to disk."""
    filename = os.path.join(DATA_DIR, f"{project}_page_{page_num}.json")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Saved {filename}")
    except Exception as e:
        logger.error(f"Failed to save {filename}: {e}")
        raise

def is_page_scraped(project, page_num):
    """Checks if we already have this page (Resumption Logic)."""
    filename = os.path.join(DATA_DIR, f"{project}_page_{page_num}.json")
    return os.path.exists(filename)

def scrape_project(session, project_key):
    """Scrape all issues from a specific Jira project."""
    logger.info(f"Starting scrape for {project_key}")
    
    # JQL (Jira Query Language) to get issues
    jql = f'project = {project_key} ORDER BY created DESC'
    
    start_at = 0
    page_num = 0
    
    # Progress bar
    pbar = tqdm(total=MAX_RESULTS_PER_PROJECT, desc=f"Fetching {project_key}")

    while start_at < MAX_RESULTS_PER_PROJECT:
        # 1. Check for Resumption
        if is_page_scraped(project_key, page_num):
            logger.debug(f"Page {page_num} already exists for {project_key}. Skipping...")
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
            
            logger.debug(f"Fetching {project_key} at startAt={start_at}")
            response = session.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            
            # Validate response structure
            data = response.json()
            if not isinstance(data, dict):
                logger.error(f"Invalid response structure for {project_key}: expected dict, got {type(data)}")
                break
            
            issues = data.get("issues", [])
            
            # Handle empty results
            if not issues:
                if start_at == 0:
                    logger.warning(f"No issues found for project {project_key}")
                else:
                    logger.info(f"Reached end of results for {project_key} at {start_at}")
                break
            
            # Validate each issue has required fields
            valid_issues = []
            for issue in issues:
                if not issue.get('key'):
                    logger.warning(f"Issue missing 'key' field in {project_key}, skipping")
                    continue
                if not issue.get('fields'):
                    logger.warning(f"Issue {issue.get('key')} missing 'fields' object, skipping")
                    continue
                valid_issues.append(issue)
            
            if not valid_issues:
                logger.warning(f"No valid issues in {project_key} page {page_num}, moving to next page")
                start_at += RESULTS_PER_PAGE
                page_num += 1
                pbar.update(RESULTS_PER_PAGE)
                continue
            
            # 3. Save Data
            save_page(project_key, page_num, valid_issues)
            logger.info(f"Saved {len(valid_issues)} issues from {project_key} page {page_num}")
            
            # Update counters
            start_at += len(issues)
            page_num += 1
            pbar.update(len(issues))
            
            # 4. Rate Limiting (Politeness)
            time.sleep(0.5)

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {project_key} at startAt={start_at}. Retrying after 5s...")
            time.sleep(5)
            continue
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limited on {project_key}. Waiting 60 seconds...")
                time.sleep(60)
                continue
            else:
                logger.error(f"HTTP error {e.response.status_code} for {project_key}: {e}")
                break
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {project_key} at startAt={start_at}: {e}")
            break
            
        except Exception as e:
            logger.error(f"Unexpected error fetching {project_key} at startAt={start_at}: {e}", exc_info=True)
            break
            
    pbar.close()
    logger.info(f"Completed scraping {project_key}")

def main():
    """Main entry point for the scraper."""
    logger.info("=== Apache Jira Scraper Started ===")
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        logger.info(f"Created data directory: {DATA_DIR}")
        
    session = get_session()
    
    for project in PROJECTS:
        try:
            scrape_project(session, project)
        except Exception as e:
            logger.error(f"Failed to scrape project {project}: {e}")
            continue
    
    logger.info("=== Scraping Complete! ===")
    logger.info(f"Raw data collected in '{DATA_DIR}/' directory")
    logger.info(f"Check 'scraper.log' for detailed logs")

if __name__ == "__main__":
    main()
