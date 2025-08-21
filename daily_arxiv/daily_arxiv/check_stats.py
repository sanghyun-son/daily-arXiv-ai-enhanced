#!/usr/bin/env python3
"""
Script to check Scrapy crawling statistics
Used to get deduplication check status results

Features:
- Check duplication between specified date and historical paper data
- Remove duplicate papers, keep new content
- Decide workflow continuation based on deduplication results
"""
import json
import sys
import os
import argparse
from datetime import datetime, timedelta


def load_papers_data(file_path):
    """
    Load complete paper data from jsonl file

    Args:
        file_path (str): JSONL file path

    Returns:
        list: List of paper data
        set: Set of paper IDs
    """
    if not os.path.exists(file_path):
        return [], set()

    papers = []
    ids = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    papers.append(data)
                    ids.add(data.get("id", ""))
        return papers, ids
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return [], set()


def save_papers_data(papers, file_path):
    """
    Save paper data to jsonl file

    Args:
        papers (list): List of paper data
        file_path (str): File path
    """
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            for paper in papers:
                f.write(json.dumps(paper, ensure_ascii=False) + "\n")
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}", file=sys.stderr)
        return False


def perform_deduplication(target_date):
    """
    Perform deduplication over multiple past days for a specific date

    Args:
        target_date (str): Target date in YYYY-MM-DD format

    Returns:
        str: Deduplication status
             - "has_new_content": Has new content
             - "no_new_content": No new content
             - "no_data": No data
             - "error": Processing error
    """

    # Try different possible paths for the data file
    possible_paths = [
        f"data/{target_date}.jsonl",  # From root directory
        f"../data/{target_date}.jsonl",  # From daily_arxiv/daily_arxiv/ directory
    ]

    target_file = None
    for path in possible_paths:
        if os.path.exists(path):
            target_file = path
            break

    if target_file is None:
        print(
            f"Data file for {target_date} does not exist in any expected location",
            file=sys.stderr,
        )
        return "no_data"

    history_days = 7  # Number of days to look back for comparison

    try:
        target_papers, target_ids = load_papers_data(target_file)
        print(
            f"Total papers for {target_date}: {len(target_papers)}",
            file=sys.stderr,
        )

        if not target_papers:
            return "no_data"

        # Collect historical IDs from past days
        history_ids = set()
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        for i in range(1, history_days + 1):
            date_str = (target_dt - timedelta(days=i)).strftime("%Y-%m-%d")
            # Try different possible paths for history files
            history_file = None
            for path in [f"data/{date_str}.jsonl", f"../data/{date_str}.jsonl"]:
                if os.path.exists(path):
                    history_file = path
                    break
            if history_file:
                _, past_ids = load_papers_data(history_file)
                history_ids.update(past_ids)

        print(
            f"History {history_days} days deduplication library size: {len(history_ids)}",
            file=sys.stderr,
        )

        duplicate_ids = target_ids & history_ids

        if duplicate_ids:
            print(
                f"Found {len(duplicate_ids)} historical duplicate papers",
                file=sys.stderr,
            )
            new_papers = [
                paper
                for paper in target_papers
                if paper.get("id", "") not in duplicate_ids
            ]

            print(
                f"Remaining papers after deduplication: {len(new_papers)}",
                file=sys.stderr,
            )

            if new_papers:
                if save_papers_data(new_papers, target_file):
                    print(
                        f"Updated {target_date} file, removed {len(duplicate_ids)} duplicate papers",
                        file=sys.stderr,
                    )
                    return "has_new_content"
                else:
                    print("Failed to save deduplicated data", file=sys.stderr)
                    return "error"
            else:
                try:
                    os.remove(target_file)
                    print(
                        f"All papers are duplicate content, deleted {target_date} file",
                        file=sys.stderr,
                    )
                except Exception as e:
                    print(f"Failed to delete file: {e}", file=sys.stderr)
                return "no_new_content"
        else:
            print("All content is new", file=sys.stderr)
            return "has_new_content"

    except Exception as e:
        print(f"Deduplication processing failed: {e}", file=sys.stderr)
        return "error"


def main():
    """
    Check deduplication status and return corresponding exit code

    Exit code meanings:
    0: Has new content, continue processing
    1: No new content, stop workflow
    2: Processing error
    """

    parser = argparse.ArgumentParser(
        description="Check deduplication status for a specific date"
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Target date in YYYY-MM-DD format (default: today)",
    )
    args = parser.parse_args()

    # Use provided date or default to today
    if args.date:
        target_date = args.date
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    print(
        f"Performing intelligent deduplication check for {target_date}...",
        file=sys.stderr,
    )

    # Perform deduplication processing
    dedup_status = perform_deduplication(target_date)

    if dedup_status == "has_new_content":
        print(
            "✅ Deduplication completed, new content found, continue workflow",
            file=sys.stderr,
        )
        sys.exit(0)
    elif dedup_status == "no_new_content":
        print(
            "⏹️ Deduplication completed, no new content, stop workflow",
            file=sys.stderr,
        )
        sys.exit(1)
    elif dedup_status == "no_data":
        print(f"⏹️ No data for {target_date}, stop workflow", file=sys.stderr)
        sys.exit(1)
    elif dedup_status == "error":
        print(
            "❌ Deduplication processing error, stop workflow", file=sys.stderr
        )
        sys.exit(2)
    else:
        # Unexpected case: unknown status
        print("❌ Unknown deduplication status, stop workflow", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
