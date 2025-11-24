import os
import json
import re

DATA_DIR = "data"
OUTPUT_FILE = "apache_jira_dataset.jsonl"

def clean_text(text):
    """Removes extra whitespace and basic cleanup."""
    if not text:
        return ""
    # Remove newlines and extra spaces for cleaner one-line JSONL
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def format_for_llm(issue):
    """
    Transforms a Jira issue into an Instruction-Input-Output format.
    """
    fields = issue.get('fields', {})
    
    # Extract basic fields
    key = issue.get('key')
    summary = clean_text(fields.get('summary', ''))
    description = clean_text(fields.get('description', ''))
    status = fields.get('status', {}).get('name', 'Unknown')
    priority = fields.get('priority', {}).get('name', 'Unknown')
    
    # --- NEW: Extract Comments ---
    comments_list = []
    raw_comments = fields.get('comment', {}).get('comments', [])
    for comment in raw_comments:
        body = clean_text(comment.get('body', ''))
        if body:
            comments_list.append(f"- {body}")
    
    comments_text = " ".join(comments_list)
    if not comments_text:
        comments_text = "No comments."
    
    # Construct the LLM training prompt
    # We combine Title, Description, and Comments into the Input
    prompt = f"Title: {summary}\nDescription: {description}\nComments: {comments_text}"
    
    # JSONL Structure
    entry = {
        "meta": {
            "source": "Apache Jira",
            "id": key,
            "url": f"https://issues.apache.org/jira/browse/{key}"
        },
        "instruction": "Analyze the issue description and discussion to determine the current status and priority.",
        "input": prompt,
        "output": f"Status: {status}\nPriority: {priority}"
    }
    
    return entry

def main():
    print("Processing raw data...")
    
    unique_ids = set()
    count = 0
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
        for filename in sorted(os.listdir(DATA_DIR)):
            if not filename.endswith(".json"):
                continue
                
            filepath = os.path.join(DATA_DIR, filename)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                try:
                    issues = json.load(f)
                    for issue in issues:
                        if issue['key'] in unique_ids:
                            continue
                        unique_ids.add(issue['key'])
                        
                        jsonl_entry = format_for_llm(issue)
                        
                        out_f.write(json.dumps(jsonl_entry) + "\n")
                        count += 1
                except json.JSONDecodeError:
                    print(f"Skipping corrupted file: {filename}")

    print(f"Done! Processed {count} issues into {OUTPUT_FILE}")

if __name__ == "__main__":
    main()