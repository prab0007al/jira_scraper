"""
Validation script to check the quality and correctness of the generated JSONL dataset.
Run this after executing processor.py to ensure data quality.
"""

import json
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

OUTPUT_FILE = "apache_jira_dataset.jsonl"
REQUIRED_FIELDS = ['meta', 'instruction', 'input', 'output']
REQUIRED_META_FIELDS = ['source', 'id', 'url', 'task']
VALID_TASKS = ['classification', 'summarization', 'qna', 'root_cause_analysis']

def validate_jsonl():
    """Validate the output JSONL file structure and content."""
    
    if not os.path.exists(OUTPUT_FILE):
        logger.error(f"Output file '{OUTPUT_FILE}' not found. Run processor.py first.")
        return False
    
    errors = []
    warnings = []
    line_count = 0
    task_counts = {task: 0 for task in VALID_TASKS}
    issue_ids = set()
    
    logger.info(f"Validating {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            line_count = i
            
            # Check if line is valid JSON
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as e:
                errors.append(f"Line {i}: Invalid JSON - {e}")
                continue
            
            # Check required top-level fields
            for field in REQUIRED_FIELDS:
                if field not in entry:
                    errors.append(f"Line {i}: Missing required field '{field}'")
            
            # Check meta fields
            if 'meta' in entry:
                meta = entry['meta']
                
                for field in REQUIRED_META_FIELDS:
                    if field not in meta:
                        errors.append(f"Line {i}: Missing required meta field '{field}'")
                
                # Validate task type
                task = meta.get('task')
                if task and task not in VALID_TASKS:
                    warnings.append(f"Line {i}: Unknown task type '{task}'")
                elif task:
                    task_counts[task] += 1
                
                # Collect issue IDs
                if 'id' in meta:
                    issue_ids.add(meta['id'])
            
            # Check for empty fields
            if 'instruction' in entry and not entry['instruction'].strip():
                warnings.append(f"Line {i}: Empty instruction field")
            
            if 'input' in entry and not entry['input'].strip():
                warnings.append(f"Line {i}: Empty input field")
            
            if 'output' in entry and not entry['output'].strip():
                warnings.append(f"Line {i}: Empty output field")
    
    # Print results
    logger.info("=" * 50)
    logger.info("VALIDATION RESULTS")
    logger.info("=" * 50)
    
    logger.info(f"\nTotal lines: {line_count}")
    logger.info(f"Unique issues: {len(issue_ids)}")
    logger.info(f"\nTask distribution:")
    for task, count in task_counts.items():
        logger.info(f"  {task}: {count}")
    
    if errors:
        logger.error(f"\n❌ Found {len(errors)} ERRORS:")
        for error in errors[:20]:  # Show first 20 errors
            logger.error(f"  {error}")
        if len(errors) > 20:
            logger.error(f"  ... and {len(errors) - 20} more errors")
        return False
    else:
        logger.info("\n✅ No errors found!")
    
    if warnings:
        logger.warning(f"\n⚠️  Found {len(warnings)} WARNINGS:")
        for warning in warnings[:10]:  # Show first 10 warnings
            logger.warning(f"  {warning}")
        if len(warnings) > 10:
            logger.warning(f"  ... and {len(warnings) - 10} more warnings")
    else:
        logger.info("✅ No warnings!")
    
    logger.info("\n" + "=" * 50)
    logger.info("VALIDATION COMPLETE")
    logger.info("=" * 50)
    
    return True

def sample_entries():
    """Display sample entries from each task type."""
    logger.info("\nSample entries:")
    logger.info("=" * 50)
    
    samples = {task: None for task in VALID_TASKS}
    
    with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                entry = json.loads(line)
                task = entry.get('meta', {}).get('task')
                
                if task in samples and samples[task] is None:
                    samples[task] = entry
                
                # Break if we have samples for all tasks
                if all(v is not None for v in samples.values()):
                    break
                    
            except json.JSONDecodeError:
                continue
    
    for task, entry in samples.items():
        if entry:
            logger.info(f"\n{task.upper()}:")
            logger.info(f"  ID: {entry['meta']['id']}")
            logger.info(f"  Instruction: {entry['instruction'][:80]}...")
            logger.info(f"  Input length: {len(entry['input'])} chars")
            logger.info(f"  Output length: {len(entry['output'])} chars")

if __name__ == "__main__":
    is_valid = validate_jsonl()
    
    if is_valid:
        sample_entries()
        logger.info("\n✅ Dataset is ready for LLM training!")
    else:
        logger.error("\n❌ Please fix errors before using the dataset.")
