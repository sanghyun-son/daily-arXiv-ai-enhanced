import os
import json
import sys
import time
from typing import List, Dict, Optional
import argparse
import dotenv
from openai import OpenAI

if os.path.exists(".env"):
    dotenv.load_dotenv()


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data", type=str, required=True, help="original jsonline data file"
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for batch completion if not ready",
    )
    parser.add_argument(
        "--max_wait",
        type=int,
        default=3600,
        help="Maximum wait time in seconds (default: 1 hour)",
    )
    parser.add_argument(
        "--no_fail",
        action="store_true",
        help="Do not exit with error code 1 when batch job is not found (for workflows)",
    )
    return parser.parse_args()


def check_batch_status(batch_job_id: str) -> Dict:
    """Check the status of a batch job"""
    client = OpenAI()
    batch_job = client.batches.retrieve(batch_job_id)

    return {
        "id": batch_job.id,
        "status": batch_job.status,
        "created_at": batch_job.created_at,
        "completed_at": batch_job.completed_at,
        "failed_at": batch_job.failed_at,
        "expired_at": batch_job.expired_at,
        "request_counts": batch_job.request_counts,
        "output_file_id": batch_job.output_file_id,
        "error_file_id": batch_job.error_file_id,
    }


def download_batch_results(output_file_id: str, output_path: str) -> bool:
    """Download batch results from OpenAI"""
    try:
        client = OpenAI()
        file_response = client.files.content(output_file_id)

        with open(output_path, "wb") as f:
            f.write(file_response.content)

        print(f"Downloaded batch results to: {output_path}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Error downloading batch results: {e}", file=sys.stderr)
        return False


def parse_batch_results(results_file: str) -> Dict[str, Dict]:
    """Parse batch results and return a mapping of custom_id to result"""
    results = {}
    error_count = 0
    function_call_count = 0
    no_function_call_count = 0

    with open(results_file, "r") as f:
        for line in f:
            result = json.loads(line)
            custom_id = result["custom_id"]

            # Debug: Print first few results to understand structure
            if len(results) < 3:
                print(
                    f"DEBUG: Result structure for {custom_id}:", file=sys.stderr
                )
                print(
                    f"  Response keys: {list(result['response'].keys())}",
                    file=sys.stderr,
                )
                if "body" in result["response"]:
                    print(
                        f"  Body keys: {list(result['response']['body'].keys())}",
                        file=sys.stderr,
                    )
                    if "choices" in result["response"]["body"]:
                        print(
                            f"  Choices length: {len(result['response']['body']['choices'])}",
                            file=sys.stderr,
                        )
                        if result["response"]["body"]["choices"]:
                            choice = result["response"]["body"]["choices"][0]
                            print(
                                f"  Choice keys: {list(choice.keys())}",
                                file=sys.stderr,
                            )
                            if "message" in choice:
                                print(
                                    f"  Message keys: {list(choice['message'].keys())}",
                                    file=sys.stderr,
                                )

            # Extract the function call result
            try:
                message = result["response"]["body"]["choices"][0]["message"]

                # Check for function_call (old format) or tool_calls (new format)
                function_call = None
                if message.get("function_call"):
                    function_call = message["function_call"]
                    function_call_count += 1
                elif (
                    message.get("tool_calls") and len(message["tool_calls"]) > 0
                ):
                    # New format: tool_calls array
                    tool_call = message["tool_calls"][0]
                    if (
                        tool_call.get("type") == "function"
                        and tool_call["function"]["name"] == "Structure"
                    ):
                        function_call = tool_call["function"]
                        function_call_count += 1

                if function_call and function_call.get("name") == "Structure":
                    try:
                        ai_result = json.loads(function_call["arguments"])
                        # Ensure relevance field exists for legacy compatibility
                        if "relevance" not in ai_result:
                            ai_result["relevance"] = "Error"
                        results[custom_id] = ai_result
                    except json.JSONDecodeError as e:
                        print(
                            f"Error parsing function call arguments for {custom_id}: {e}",
                            file=sys.stderr,
                        )
                        print(
                            f"  Arguments: {function_call['arguments'][:200]}...",
                            file=sys.stderr,
                        )
                        error_count += 1
                        results[custom_id] = {
                            "tldr": "Error parsing result",
                            "motivation": "Error parsing result",
                            "method": "Error parsing result",
                            "result": "Error parsing result",
                            "conclusion": "Error parsing result",
                            "relevance": "Error",
                        }
                else:
                    no_function_call_count += 1
                    print(
                        f"No Structure function call found for {custom_id}",
                        file=sys.stderr,
                    )
                    # Debug: Print what we found instead
                    if len(results) < 3:
                        print(
                            f"  Message content: {message.get('content', 'No content')[:100]}...",
                            file=sys.stderr,
                        )
                        if message.get("tool_calls"):
                            print(
                                f"  Tool calls: {message['tool_calls']}",
                                file=sys.stderr,
                            )
                    results[custom_id] = {
                        "tldr": "No AI result",
                        "motivation": "No AI result",
                        "method": "No AI result",
                        "result": "No AI result",
                        "conclusion": "No AI result",
                        "relevance": "Error",
                    }
            except (KeyError, IndexError) as e:
                error_count += 1
                print(
                    f"Error accessing response structure for {custom_id}: {e}",
                    file=sys.stderr,
                )
                results[custom_id] = {
                    "tldr": "Error accessing result",
                    "motivation": "Error accessing result",
                    "method": "Error accessing result",
                    "result": "Error accessing result",
                    "conclusion": "Error accessing result",
                    "relevance": "Error",
                }

    # Print summary statistics
    print(f"Parsing summary:", file=sys.stderr)
    print(f"  Total results: {len(results)}", file=sys.stderr)
    print(f"  Function calls found: {function_call_count}", file=sys.stderr)
    print(f"  No function calls: {no_function_call_count}", file=sys.stderr)
    print(f"  Parsing errors: {error_count}", file=sys.stderr)

    return results


def process_batch_results(
    data_file: str, wait_for_completion: bool = False, max_wait: int = 3600
) -> bool:
    """Process batch results and create the enhanced data file"""
    # Load batch info
    batch_info_file = data_file.replace(".jsonl", "_batch_info.json")
    if not os.path.exists(batch_info_file):
        print(f"Batch info file not found: {batch_info_file}", file=sys.stderr)
        print(
            "This is normal if the batch job hasn't been submitted yet or is still processing",
            file=sys.stderr,
        )
        return False

    with open(batch_info_file, "r") as f:
        batch_info = json.load(f)

    batch_job_id = batch_info["batch_job_id"]
    language = batch_info.get("language", "Korean")

    print(f"Checking batch job: {batch_job_id}", file=sys.stderr)

    # Check batch status
    wait_time = 0
    while True:
        status_info = check_batch_status(batch_job_id)
        print(f'Batch status: {status_info["status"]}', file=sys.stderr)

        if status_info["status"] == "completed":
            break
        elif status_info["status"] in ["failed", "expired", "cancelled"]:
            print(
                f'Batch job failed with status: {status_info["status"]}',
                file=sys.stderr,
            )
            return False
        elif status_info["status"] in [
            "validating",
            "in_progress",
            "finalizing",
        ]:
            if wait_for_completion and wait_time < max_wait:
                print(
                    f"Batch job still processing, waiting... ({wait_time}s elapsed)",
                    file=sys.stderr,
                )
                time.sleep(60)  # Wait 1 minute
                wait_time += 60
            else:
                if wait_for_completion:
                    print(
                        f"Maximum wait time ({max_wait}s) exceeded",
                        file=sys.stderr,
                    )
                else:
                    print(
                        "Batch job not ready yet. Use --wait flag to wait for completion.",
                        file=sys.stderr,
                    )
                return False
        else:
            print(
                f'Unknown batch status: {status_info["status"]}',
                file=sys.stderr,
            )
            return False

    # Download results
    if not status_info["output_file_id"]:
        print("No output file ID found in completed batch job", file=sys.stderr)
        return False

    results_file = data_file.replace(".jsonl", "_batch_results.jsonl")
    if not download_batch_results(status_info["output_file_id"], results_file):
        return False

    # Parse results
    ai_results = parse_batch_results(results_file)
    print(f"Parsed {len(ai_results)} AI results", file=sys.stderr)

    # Load original data
    data = []
    with open(data_file, "r") as f:
        for line in f:
            data.append(json.loads(line))

    # Merge AI results with original data
    enhanced_data = []
    for item in data:
        if item["id"] in ai_results:
            item["AI"] = ai_results[item["id"]]
        else:
            print(f'No AI result found for {item["id"]}', file=sys.stderr)
            item["AI"] = {
                "tldr": "No AI result",
                "motivation": "No AI result",
                "method": "No AI result",
                "result": "No AI result",
                "conclusion": "No AI result",
            }
        enhanced_data.append(item)

    # Filter out low/irrelevant papers and count relevance distribution
    relevance_counts = {
        "Must": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
        "Irrelevant": 0,
        "Error": 0,
        "Legacy": 0,
    }
    filtered_data = []

    for item in enhanced_data:
        try:
            # Legacy compatibility: check if AI field exists and has relevance
            if "AI" not in item:
                relevance_counts["Legacy"] += 1
                filtered_data.append(item)  # Include legacy items
                continue

            ai_data = item["AI"]

            # Check if relevance field exists
            if "relevance" not in ai_data:
                relevance_counts["Legacy"] += 1
                filtered_data.append(
                    item
                )  # Include items without relevance field
                continue

            relevance = ai_data["relevance"]

            # Count relevance distribution
            if relevance in relevance_counts:
                relevance_counts[relevance] += 1
            else:
                relevance_counts["Error"] += 1

            # Filter out low and irrelevant papers
            if relevance in ["Low", "Irrelevant"]:
                print(
                    f"Filtering out paper {item['id']} with relevance: {relevance}",
                    file=sys.stderr,
                )
                continue

            filtered_data.append(item)

        except Exception as e:
            print(
                f"Error processing item {item.get('id', 'unknown')}: {e}",
                file=sys.stderr,
            )
            relevance_counts["Error"] += 1
            filtered_data.append(item)  # Include items with errors

    # Print relevance distribution
    print("\n=== Relevance Distribution ===", file=sys.stderr)
    total_processed = len(enhanced_data)
    total_filtered = len(filtered_data)
    total_excluded = total_processed - total_filtered

    for relevance, count in relevance_counts.items():
        percentage = (
            (count / total_processed * 100) if total_processed > 0 else 0
        )
        print(f"{relevance}: {count} ({percentage:.1f}%)", file=sys.stderr)

    print(f"\nTotal processed: {total_processed}", file=sys.stderr)
    print(f"Total included: {total_filtered}", file=sys.stderr)
    print(f"Total excluded: {total_excluded}", file=sys.stderr)
    print(
        f"Exclusion rate: {(total_excluded/total_processed*100):.1f}%",
        file=sys.stderr,
    )

    # Sort papers by relevance (Must > High > Medium > Low/Irrelevant/Error)
    relevance_order = {
        "Must": 3,
        "High": 2,
        "Medium": 1,
        "Low": 0,
        "Irrelevant": 0,
        "Error": 0,
    }

    def get_relevance_score(item):
        """Get relevance score for sorting"""
        try:
            if "AI" in item and "relevance" in item["AI"]:
                relevance = item["AI"]["relevance"]
                # Handle special cases: Error, Irrelevant, Low, and any unknown values get priority 0
                if relevance in ["Error", "Irrelevant", "Low"]:
                    return 0
                return relevance_order.get(relevance, 0)
            return 0
        except:
            return 0

    # Sort filtered data by relevance (highest first)
    filtered_data.sort(key=get_relevance_score, reverse=True)

    print(
        f"\nSorted papers by relevance (Must > High > Medium > Low/Irrelevant/Error)",
        file=sys.stderr,
    )

    # Save filtered results
    target_file = data_file.replace(".jsonl", f"_AI_enhanced_{language}.jsonl")
    if os.path.exists(target_file):
        os.remove(target_file)
        print(f"Removed existing file: {target_file}", file=sys.stderr)

    with open(target_file, "w") as f:
        for item in filtered_data:
            f.write(json.dumps(item) + "\n")

    print(f"Created enhanced data file: {target_file}", file=sys.stderr)

    # Clean up temporary files
    if os.path.exists(results_file):
        os.remove(results_file)
        print(f"Cleaned up results file: {results_file}", file=sys.stderr)

    # Clean up batch-related temporary files
    batch_files_to_cleanup = [
        batch_info.get("batch_requests_file", ""),
        batch_info_file,
        data_file.replace(".jsonl", "_batch_submitted.txt"),
    ]

    for file_path in batch_files_to_cleanup:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Cleaned up: {file_path}", file=sys.stderr)
            except Exception as e:
                print(
                    f"Warning: Could not clean up {file_path}: {e}",
                    file=sys.stderr,
                )

    return True


def main():
    args = parse_args()

    success = process_batch_results(
        args.data, wait_for_completion=args.wait, max_wait=args.max_wait
    )

    if success:
        print("Batch processing completed successfully")
        sys.exit(0)
    else:
        if args.no_fail:
            print("Batch processing failed but continuing (no_fail mode)")
            sys.exit(0)
        else:
            print("Batch processing failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
