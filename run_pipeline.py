#!/usr/bin/env python3
"""
Pipeline runner for Jira scraper and processor.
Runs scraper.py followed by processor.py in sequence.
Works on Windows, Linux, and macOS.
"""

import subprocess
import sys
import os

def run_command(script_name):
    """Run a Python script and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running {script_name}...")
    print('='*60)
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            check=True,
            text=True
        )
        print(f"\n✅ {script_name} completed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error running {script_name}")
        print(f"Exit code: {e.returncode}")
        return False
        
    except FileNotFoundError:
        print(f"\n❌ {script_name} not found in current directory")
        return False
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False

def main():
    """Main pipeline execution."""
    print("="*60)
    print("Apache Jira Scraper - Full Pipeline")
    print("="*60)
    
    # Check if scripts exist
    if not os.path.exists('scraper.py'):
        print("❌ scraper.py not found!")
        sys.exit(1)
        
    if not os.path.exists('processor.py'):
        print("❌ processor.py not found!")
        sys.exit(1)
    
    # Step 1: Run scraper
    if not run_command('scraper.py'):
        print("\n❌ Pipeline failed at scraping stage")
        sys.exit(1)
    
    # Step 2: Run processor
    if not run_command('processor.py'):
        print("\n❌ Pipeline failed at processing stage")
        sys.exit(1)
    
    # Success
    print("\n" + "="*60)
    print("🎉 Pipeline completed successfully!")
    print("="*60)
    print("\nGenerated files:")
    print("  - data/ directory with raw JSON files")
    print("  - apache_jira_dataset.jsonl")
    print("  - scraper.log")
    print("\nRun 'python test_validation.py' to verify output quality.")

if __name__ == "__main__":
    main()
