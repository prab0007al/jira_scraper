# Apache Jira Web Scraper & Dataset Curator

## Overview
This project scrapes public issue tracking data from the Apache Software Foundation's Jira instance and processes it into a JSONL format suitable for training Large Language Models (LLMs).

## Architecture

### 1. Data Collection (`scraper.py`)
* **Source:** Apache Jira REST API (v2).
* **Method:** Pagination using `startAt` and `maxResults`.
* **Resilience:**
    * **Retries:** Uses `HTTPAdapter` with exponential backoff to handle 429 (Rate Limit) and 5xx errors.
    * **Checkpointing:** Saves data in chunks (per page) to the `data/` directory. If the script is stopped, it checks for existing files and skips those pages upon restart.
* **Politeness:** Includes a `time.sleep(0.5)` delay between requests to respect server load.

### 2. Data Transformation (`processor.py`)
* **Input:** Raw JSON files from `data/`.
* **Output:** `apache_jira_dataset.jsonl`.
* **Logic:** * Deduplicates issues based on issue Key.
    * Cleans whitespace from descriptions.
    * Formats data into an `instruction`, `input`, `output` schema for supervised fine-tuning.

## How to Run

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the Scraper:**
    ```bash
    python scraper.py
    ```
    *This will populate the `data/` folder.*

3.  **Run the Processor:**
    ```bash
    python processor.py
    ```
    *This will generate `apache_jira_dataset.jsonl`.*

## Derived Tasks
The dataset is structured to train a model on **Issue Classification**:
* **Input:** The issue Title and Description.
* **Output:** The issue Status (e.g., "Resolved") and Priority (e.g., "Major").