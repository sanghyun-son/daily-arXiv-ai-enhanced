"""Example tests for ai/process_batch.py using the mock OpenAI server with relevance control."""

import json
import tempfile
from unittest.mock import patch

import pytest
import requests


class TestEnhanceWithMockServer:
    """Example tests showing how to use the mock server with relevance control."""

    def test_filtering_high_relevance_papers(
        self, openai_mock_server, openai_base_url
    ):
        """Test that high relevance papers are included in the final output."""
        # Set relevance to "High" to simulate relevant papers
        openai_mock_server.set_relevance_override("High")

        # Create test data
        test_data = [
            {"id": "test1", "summary": "Important AI research paper"},
            {"id": "test2", "summary": "Another relevant paper"},
        ]

        # This would be the actual process_batch.py logic, but we're simulating it
        processed_data = []

        for item in test_data:
            # Simulate the AI processing step
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
            args = json.loads(
                data["choices"][0]["message"]["tool_calls"][0]["function"][
                    "arguments"
                ]
            )

            # Add AI analysis to item
            item["AI"] = args
            processed_data.append(item)

        # Simulate filtering logic (from process_batch.py)
        filtered_data = []
        for item in processed_data:
            relevance = item["AI"]["relevance"]
            if relevance not in ["Low", "Irrelevant"]:
                filtered_data.append(item)

        # High relevance papers should be included
        assert len(filtered_data) == 2
        assert all(item["AI"]["relevance"] == "High" for item in filtered_data)

    def test_filtering_low_relevance_papers(
        self, openai_mock_server, openai_base_url
    ):
        """Test that low relevance papers are filtered out."""
        # Set relevance to "Low" to simulate irrelevant papers
        openai_mock_server.set_relevance_override("Low")

        # Create test data
        test_data = [
            {"id": "test1", "summary": "Unrelated research paper"},
            {"id": "test2", "summary": "Another irrelevant paper"},
        ]

        processed_data = []

        for item in test_data:
            # Simulate the AI processing step
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
            args = json.loads(
                data["choices"][0]["message"]["tool_calls"][0]["function"][
                    "arguments"
                ]
            )

            item["AI"] = args
            processed_data.append(item)

        # Simulate filtering logic
        filtered_data = []
        for item in processed_data:
            relevance = item["AI"]["relevance"]
            if relevance not in ["Low", "Irrelevant"]:
                filtered_data.append(item)

        # Low relevance papers should be filtered out
        assert len(filtered_data) == 0

    def test_mixed_relevance_scenario(
        self, openai_mock_server, openai_base_url
    ):
        """Test a scenario with mixed relevance levels."""
        test_data = [
            {"id": "test1", "summary": "Important AI paper"},
            {"id": "test2", "summary": "Unrelated paper"},
            {"id": "test3", "summary": "Medium relevance paper"},
        ]

        processed_data = []

        # Process each item with different relevance levels
        relevance_levels = ["High", "Low", "Medium"]

        for i, item in enumerate(test_data):
            # Set different relevance for each item
            openai_mock_server.set_relevance_override(relevance_levels[i])

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
            args = json.loads(
                data["choices"][0]["message"]["tool_calls"][0]["function"][
                    "arguments"
                ]
            )

            item["AI"] = args
            processed_data.append(item)

        # Simulate filtering logic
        filtered_data = []
        for item in processed_data:
            relevance = item["AI"]["relevance"]
            if relevance not in ["Low", "Irrelevant"]:
                filtered_data.append(item)

        # Only High and Medium relevance papers should remain
        assert len(filtered_data) == 2
        relevances = [item["AI"]["relevance"] for item in filtered_data]
        assert "High" in relevances
        assert "Medium" in relevances
        assert "Low" not in relevances

    def test_relevance_distribution_tracking(
        self, openai_mock_server, openai_base_url
    ):
        """Test tracking relevance distribution statistics."""
        # Create test data with known relevance distribution
        test_data = [
            {"id": f"test{i}", "summary": f"Paper {i}"} for i in range(10)
        ]

        # Define relevance distribution: 2 Must, 3 High, 2 Medium, 2 Low, 1 Irrelevant
        relevance_distribution = [
            "Must",
            "Must",
            "High",
            "High",
            "High",
            "Medium",
            "Medium",
            "Low",
            "Low",
            "Irrelevant",
        ]

        processed_data = []
        relevance_counts = {
            "Must": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
            "Irrelevant": 0,
        }

        for i, item in enumerate(test_data):
            # Set relevance for this item
            relevance = relevance_distribution[i]
            openai_mock_server.set_relevance_override(relevance)

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
            args = json.loads(
                data["choices"][0]["message"]["tool_calls"][0]["function"][
                    "arguments"
                ]
            )

            item["AI"] = args
            processed_data.append(item)

            # Track relevance distribution
            relevance_counts[args["relevance"]] += 1

        # Verify relevance distribution
        assert relevance_counts["Must"] == 2
        assert relevance_counts["High"] == 3
        assert relevance_counts["Medium"] == 2
        assert relevance_counts["Low"] == 2
        assert relevance_counts["Irrelevant"] == 1

        # Simulate filtering and verify final counts
        filtered_data = []
        for item in processed_data:
            relevance = item["AI"]["relevance"]
            if relevance not in ["Low", "Irrelevant"]:
                filtered_data.append(item)

        # Should have 7 items after filtering (Must + High + Medium)
        assert len(filtered_data) == 7
