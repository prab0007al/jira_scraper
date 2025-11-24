import os
import json
import re
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DATA_DIR = "data"
OUTPUT_FILE = "apache_jira_dataset.jsonl"

def clean_text(text):
    """Removes extra whitespace and basic cleanup."""
    if not text:
        return ""
    # Remove excessive newlines and spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def safe_get(obj, *keys, default=""):
    """Safely navigate nested dictionaries without KeyError."""
    for key in keys:
        try:
            obj = obj[key]
        except (KeyError, TypeError, AttributeError):
            return default
    return obj if obj is not None else default

def format_for_llm(issue):
    """
    Transforms a Jira issue into multiple LLM training formats.
    Returns a list of entries (one per task type).
    """
    try:
        fields = issue.get('fields', {})
        
        # Extract basic fields with safe defaults
        key = issue.get('key', 'UNKNOWN')
        summary = clean_text(safe_get(fields, 'summary', default='No title provided'))
        description = clean_text(safe_get(fields, 'description', default='No description provided'))
        status = safe_get(fields, 'status', 'name', default='Unknown')
        priority = safe_get(fields, 'priority', 'name', default='Unknown')
        
        # Extract assignee safely
        assignee = safe_get(fields, 'assignee', 'displayName', default='Unassigned')
        
        # Extract labels
        labels = fields.get('labels', [])
        labels_text = ', '.join(labels) if labels else 'None'
        
        # Extract created date
        created = safe_get(fields, 'created', default='Unknown')
        
        # Extract comments with error handling
        comments_list = []
        raw_comments = safe_get(fields, 'comment', 'comments', default=[])
        
        for comment in raw_comments:
            body = clean_text(safe_get(comment, 'body', default=''))
            author = safe_get(comment, 'author', 'displayName', default='Unknown')
            if body:
                comments_list.append(f"{author}: {body}")
        
        comments_text = " | ".join(comments_list) if comments_list else "No comments."
        
        # Create multiple task formats
        entries = []
        
        # ===== Task 1: Issue Classification =====
        classification_entry = {
            "meta": {
                "source": "Apache Jira",
                "id": key,
                "url": f"https://issues.apache.org/jira/browse/{key}",
                "task": "classification"
            },
            "instruction": "Analyze the issue description and discussion to determine the current status and priority.",
            "input": f"Title: {summary}\nDescription: {description}\nComments: {comments_text}",
            "output": f"Status: {status}\nPriority: {priority}"
        }
        entries.append(classification_entry)
        
        # ===== Task 2: Issue Summarization =====
        # Create a meaningful summary
        summary_output = f"{summary}."
        if description and description != "No description provided":
            # Add first 150 chars of description
            desc_snippet = description[:150] + "..." if len(description) > 150 else description
            summary_output += f" {desc_snippet}"
        
        summarization_entry = {
            "meta": {
                "source": "Apache Jira",
                "id": key,
                "url": f"https://issues.apache.org/jira/browse/{key}",
                "task": "summarization"
            },
            "instruction": "Generate a concise summary of this Jira issue in 1-2 sentences.",
            "input": f"Issue Key: {key}\nTitle: {summary}\nDescription: {description}\nStatus: {status}\nPriority: {priority}",
            "output": f"Summary: {summary_output}"
        }
        entries.append(summarization_entry)
        
        # ===== Task 3: Question Answering =====
        # Generate QnA pairs based on issue content
        qna_entry = {
            "meta": {
                "source": "Apache Jira",
                "id": key,
                "url": f"https://issues.apache.org/jira/browse/{key}",
                "task": "qna"
            },
            "instruction": "Answer the question based on the Jira issue information and discussion.",
            "input": f"Question: What is the current status and priority of issue {key} regarding '{summary}'?\n\nIssue Details:\nTitle: {summary}\nDescription: {description}\nComments: {comments_text}",
            "output": f"Answer: Issue {key} is currently marked as '{status}' with a priority level of '{priority}'. The issue is assigned to {assignee}. Labels: {labels_text}."
        }
        entries.append(qna_entry)
        
        # ===== Task 4: Root Cause Analysis (if comments exist) =====
        if len(comments_list) > 0:
            root_cause_entry = {
                "meta": {
                    "source": "Apache Jira",
                    "id": key,
                    "url": f"https://issues.apache.org/jira/browse/{key}",
                    "task": "root_cause_analysis"
                },
                "instruction": "Based on the issue description and team discussion, identify the root cause and proposed solution.",
                "input": f"Issue: {key}\nTitle: {summary}\nDescription: {description}\nTeam Discussion: {comments_text}",
                "output": f"The issue '{summary}' was analyzed and is currently {status}. Priority: {priority}. The team discussion provides context on resolution approaches."
            }
            entries.append(root_cause_entry)
        
        return entries
        
    except Exception as e:
        logger.error(f"Error processing issue {issue.get('key', 'UNKNOWN')}: {e}", exc_info=True)
        return []

def main():
    """Main entry point for the processor."""
    logger.info("=== Starting Data Processing ===")
    
    if not os.path.exists(DATA_DIR):
        logger.error(f"Data directory '{DATA_DIR}' not found. Run scraper.py first.")
        return
    
    unique_ids = set()
    total_entries = 0
    skipped_files = 0
    skipped_issues = 0
    
    files_to_process = [f for f in sorted(os.listdir(DATA_DIR)) if f.endswith(".json")]
    
    if not files_to_process:
        logger.error(f"No JSON files found in '{DATA_DIR}'. Run scraper.py first.")
        return
    
    logger.info(f"Found {len(files_to_process)} files to process")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
        for filename in files_to_process:
            filepath = os.path.join(DATA_DIR, filename)
            logger.info(f"Processing {filename}...")
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    issues = json.load(f)
                    
                    if not isinstance(issues, list):
                        logger.error(f"Invalid format in {filename}: expected list, got {type(issues)}")
                        skipped_files += 1
                        continue
                    
                    for issue in issues:
                        issue_key = issue.get('key')
                        
                        if not issue_key:
                            logger.warning(f"Issue missing 'key' field in {filename}, skipping")
                            skipped_issues += 1
                            continue
                        
                        # Skip duplicates
                        if issue_key in unique_ids:
                            logger.debug(f"Duplicate issue {issue_key}, skipping")
                            continue
                        
                        unique_ids.add(issue_key)
                        
                        # Generate multiple task entries for this issue
                        jsonl_entries = format_for_llm(issue)
                        
                        if not jsonl_entries:
                            logger.warning(f"No entries generated for {issue_key}")
                            skipped_issues += 1
                            continue
                        
                        # Write each task entry
                        for entry in jsonl_entries:
                            out_f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                            total_entries += 1
                            
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error in {filename}: {e}")
                skipped_files += 1
                
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}", exc_info=True)
                skipped_files += 1

    # Final statistics
    logger.info("=== Processing Complete! ===")
    logger.info(f"Output file: {OUTPUT_FILE}")
    logger.info(f"Total training entries: {total_entries}")
    logger.info(f"Unique issues processed: {len(unique_ids)}")
    logger.info(f"Skipped files: {skipped_files}")
    logger.info(f"Skipped issues: {skipped_issues}")
    
    # Calculate task distribution
    tasks_per_issue = total_entries / len(unique_ids) if unique_ids else 0
    logger.info(f"Average tasks per issue: {tasks_per_issue:.1f}")

if __name__ == "__main__":
    main()
