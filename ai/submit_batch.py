import os
import json
import sys
from typing import List, Dict
import argparse
import dotenv
from openai import OpenAI

if os.path.exists(".env"):
    dotenv.load_dotenv()

# Load templates
template = open("template.txt", "r").read()
system = open("system.txt", "r").read()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", type=str, required=True, help="jsonline data file"
    )
    return parser.parse_args()


def create_batch_requests(
    data: List[Dict], language: str, interest: str = ""
) -> List[Dict]:
    """Create batch requests for OpenAI Batch API"""
    batch_requests = []

    # Generate interest section based on whether interest is provided
    if not interest:
        interest_section = "No interest provided"
    else:
        interest_section = interest

    for item in data:
        request = {
            "custom_id": item["id"],
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": os.environ.get("MODEL_NAME", "gpt-4o-mini"),
                "messages": [
                    {
                        "role": "system",
                        "content": system.format(language=language),
                    },
                    {
                        "role": "user",
                        "content": template.format(
                            language=language,
                            interest_section=interest_section,
                            content=item["summary"],
                        ),
                    },
                ],
                "functions": [
                    {
                        "name": "Structure",
                        "description": "Analyze paper abstract and extract key information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "tldr": {
                                    "type": "string",
                                    "description": "generate a too long; didn't read summary",
                                },
                                "motivation": {
                                    "type": "string",
                                    "description": "describe the motivation in this paper",
                                },
                                "method": {
                                    "type": "string",
                                    "description": "method of this paper",
                                },
                                "result": {
                                    "type": "string",
                                    "description": "result of this paper",
                                },
                                "conclusion": {
                                    "type": "string",
                                    "description": "conclusion of this paper",
                                },
                                "relevance": {
                                    "type": "string",
                                    "description": "relevance level between the abstract and user interests: Must, High, Medium, Low, or Irrelevant",
                                },
                            },
                            "required": [
                                "tldr",
                                "motivation",
                                "method",
                                "result",
                                "conclusion",
                                "relevance",
                            ],
                        },
                    }
                ],
                "function_call": {"name": "Structure"},
            },
        }
        batch_requests.append(request)

    return batch_requests


def submit_batch_job(
    data: List[Dict], language: str, data_file: str, interest: str = ""
) -> str:
    """Submit batch job to OpenAI"""
    client = OpenAI()

    # Create batch requests
    batch_requests = create_batch_requests(data, language, interest)

    # Save batch requests to a temporary file
    batch_file_path = data_file.replace(".jsonl", "_batch_requests.jsonl")
    with open(batch_file_path, "w") as f:
        for request in batch_requests:
            f.write(json.dumps(request) + "\n")

    print(f"Created batch requests file: {batch_file_path}", file=sys.stderr)

    # Upload the batch file
    with open(batch_file_path, "rb") as f:
        batch_input_file = client.files.create(file=f, purpose="batch")

    print(
        f"Uploaded batch file with ID: {batch_input_file.id}", file=sys.stderr
    )

    # Create the batch job
    batch_job = client.batches.create(
        input_file_id=batch_input_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={
            "description": f"arXiv papers AI enhancement for {data_file}",
            "date": data_file.split("/")[-1].split(".")[
                0
            ],  # Extract date from filename
        },
    )

    print(f"Created batch job with ID: {batch_job.id}", file=sys.stderr)
    print(f"Batch job status: {batch_job.status}", file=sys.stderr)

    # Save batch job info
    batch_info_file = data_file.replace(".jsonl", "_batch_info.json")
    batch_info = {
        "batch_job_id": batch_job.id,
        "batch_input_file_id": batch_input_file.id,
        "status": batch_job.status,
        "created_at": batch_job.created_at,
        "data_file": data_file,
        "language": language,
        "batch_requests_file": batch_file_path,
    }

    with open(batch_info_file, "w") as f:
        json.dump(batch_info, f, indent=2)

    print(f"Saved batch info to: {batch_info_file}", file=sys.stderr)

    return batch_job.id


def main():
    args = parse_args()
    language = os.environ.get("LANGUAGE", "Chinese")
    interest = os.environ.get("INTEREST", "")

    # Read data
    data = []
    with open(args.data, "r") as f:
        for line in f:
            data.append(json.loads(line))

    # Remove duplicates
    seen_ids = set()
    unique_data = []
    for item in data:
        if item["id"] not in seen_ids:
            seen_ids.add(item["id"])
            unique_data.append(item)

    data = unique_data
    print(f"Processing {len(data)} unique papers", file=sys.stderr)

    # Submit batch job
    batch_job_id = submit_batch_job(data, language, args.data, interest)
    print(f"Successfully submitted batch job: {batch_job_id}")


if __name__ == "__main__":
    main()
