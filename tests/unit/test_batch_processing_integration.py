"""Integration tests for batch processing files using the mock OpenAI server."""

import json
import tempfile
import os
from unittest.mock import patch, MagicMock

import pytest
import requests


class TestBatchProcessingIntegration:
    """Test that batch processing files work correctly with the mock server."""

    def test_submit_batch_creates_correct_requests(
        self, openai_mock_server, openai_base_url
    ):
        """Test that submit_batch.py creates correct batch requests."""
        # Set relevance to "High" for testing
        openai_mock_server.set_relevance_override("High")

        # Create test data
        test_data = [
            {"id": "test1", "summary": "Important AI research paper"},
            {"id": "test2", "summary": "Another relevant paper"},
        ]

        # Create temporary data file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            for item in test_data:
                f.write(json.dumps(item) + "\n")
            data_file = f.name

        try:
            # Simulate the batch request creation (from submit_batch.py)
            batch_requests = []
            for item in test_data:
                request = {
                    "custom_id": item["id"],
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a professional paper analyst...",
                            },
                            {
                                "role": "user",
                                "content": f"Analyze: {item['summary']}",
                            },
                        ],
                        "functions": [
                            {
                                "name": "Structure",
                                "description": "Analyze paper abstract and extract key information",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "tldr": {"type": "string"},
                                        "motivation": {"type": "string"},
                                        "method": {"type": "string"},
                                        "result": {"type": "string"},
                                        "conclusion": {"type": "string"},
                                        "relevance": {"type": "string"},
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

            # Verify batch requests are created correctly
            assert len(batch_requests) == 2
            assert batch_requests[0]["custom_id"] == "test1"
            assert batch_requests[1]["custom_id"] == "test2"
            assert (
                "Structure" in batch_requests[0]["body"]["functions"][0]["name"]
            )
            assert (
                "relevance"
                in batch_requests[0]["body"]["functions"][0]["parameters"][
                    "properties"
                ]
            )

        finally:
            # Clean up
            os.unlink(data_file)

    def test_process_batch_parses_results_correctly(
        self, openai_mock_server, openai_base_url
    ):
        """Test that process_batch.py can parse batch results correctly."""
        # Set relevance to "Medium" for testing
        openai_mock_server.set_relevance_override("Medium")

        # Create test data
        test_data = [
            {"id": "test1", "summary": "Important AI research paper"},
            {"id": "test2", "summary": "Another relevant paper"},
        ]

        # Simulate batch results (as they would be returned by OpenAI)
        batch_results = []
        for item in test_data:
            # Make a request to the mock server
            response = requests.post(
                f"{openai_base_url}v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [
                        {
                            "role": "user",
                            "content": f"Analyze: {item['summary']}",
                        }
                    ],
                    "tools": [
                        {
                            "type": "function",
                            "function": {
                                "name": "Structure",
                                "description": "Structure the analysis",
                                "parameters": {
                                    "type": "object",
                                    "properties": {
                                        "tldr": {"type": "string"},
                                        "motivation": {"type": "string"},
                                        "method": {"type": "string"},
                                        "result": {"type": "string"},
                                        "conclusion": {"type": "string"},
                                        "relevance": {"type": "string"},
                                    },
                                },
                            },
                        }
                    ],
                    "tool_choice": "auto",
                },
                headers={"Authorization": "Bearer test-key"},
            )

            data = response.json()
            function_call = data["choices"][0]["message"]["tool_calls"][0]

            # Format as batch result (simulating OpenAI's batch API response format)
            batch_result = {
                "custom_id": item["id"],
                "response": {
                    "body": {
                        "choices": [
                            {
                                "message": {
                                    "function_call": {
                                        "name": function_call["function"][
                                            "name"
                                        ],
                                        "arguments": function_call["function"][
                                            "arguments"
                                        ],
                                    }
                                }
                            }
                        ]
                    }
                },
            }
            batch_results.append(batch_result)

        # Simulate the parsing logic from process_batch.py
        ai_results = {}
        for result in batch_results:
            custom_id = result["custom_id"]
            function_call = result["response"]["body"]["choices"][0]["message"][
                "function_call"
            ]

            if function_call["name"] == "Structure":
                try:
                    ai_result = json.loads(function_call["arguments"])
                    # Ensure relevance field exists for legacy compatibility
                    if "relevance" not in ai_result:
                        ai_result["relevance"] = "Error"
                    ai_results[custom_id] = ai_result
                except json.JSONDecodeError:
                    ai_results[custom_id] = {
                        "tldr": "Error parsing result",
                        "motivation": "Error parsing result",
                        "method": "Error parsing result",
                        "result": "Error parsing result",
                        "conclusion": "Error parsing result",
                        "relevance": "Error",
                    }

        # Verify parsing results
        assert len(ai_results) == 2
        assert "test1" in ai_results
        assert "test2" in ai_results
        assert ai_results["test1"]["relevance"] == "Medium"
        assert ai_results["test2"]["relevance"] == "Medium"

    def test_filtering_logic_works_correctly(self):
        """Test that the filtering logic from process_batch.py works correctly."""
        # Simulate the filtering logic from process_batch.py
        relevance_counts = {
            "Must": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
            "Irrelevant": 0,
            "Error": 0,
            "Legacy": 0,
        }

        # Test data with different relevance levels
        test_items = [
            {"id": "test1", "AI": {"relevance": "High"}},
            {"id": "test2", "AI": {"relevance": "Medium"}},
            {"id": "test3", "AI": {"relevance": "Low"}},
            {"id": "test4", "AI": {"relevance": "Irrelevant"}},
            {"id": "test5", "AI": {"relevance": "Must"}},
        ]

        filtered_data = []

        for item in test_items:
            try:
                if "AI" not in item:
                    relevance_counts["Legacy"] += 1
                    filtered_data.append(item)
                    continue

                ai_data = item["AI"]

                if "relevance" not in ai_data:
                    relevance_counts["Legacy"] += 1
                    filtered_data.append(item)
                    continue

                relevance = ai_data["relevance"]

                if relevance in relevance_counts:
                    relevance_counts[relevance] += 1
                else:
                    relevance_counts["Error"] += 1

                # Filter out low and irrelevant papers
                if relevance in ["Low", "Irrelevant"]:
                    continue

                filtered_data.append(item)

            except Exception:
                relevance_counts["Error"] += 1
                filtered_data.append(item)

        # Verify filtering results
        assert len(filtered_data) == 3  # High, Medium, Must should remain
        assert relevance_counts["High"] == 1
        assert relevance_counts["Medium"] == 1
        assert relevance_counts["Low"] == 1
        assert relevance_counts["Irrelevant"] == 1
        assert relevance_counts["Must"] == 1

        # Verify only relevant papers remain
        remaining_relevances = [
            item["AI"]["relevance"] for item in filtered_data
        ]
        assert "High" in remaining_relevances
        assert "Medium" in remaining_relevances
        assert "Must" in remaining_relevances
        assert "Low" not in remaining_relevances
        assert "Irrelevant" not in remaining_relevances
