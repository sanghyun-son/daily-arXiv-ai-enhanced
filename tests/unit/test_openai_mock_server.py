"""Tests for the OpenAI mock server."""

import json
import requests


class TestOpenAIMockServer:
    """Test the OpenAI mock server functionality."""

    def test_chat_completions_basic(self, openai_mock_server, openai_base_url):
        """Test basic chat completions endpoint."""
        response = requests.post(
            f"{openai_base_url}v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello, world!"}],
            },
            headers={"Authorization": "Bearer test-key"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["object"] == "chat.completion"
        assert data["model"] == "gpt-4"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] is not None
        assert data["choices"][0]["finish_reason"] == "stop"

    def test_chat_completions_function_calling(
        self, openai_mock_server, openai_base_url
    ):
        """Test chat completions with function calling."""
        response = requests.post(
            f"{openai_base_url}v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Analyze this paper"}],
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

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["object"] == "chat.completion"
        assert data["model"] == "gpt-4"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert data["choices"][0]["message"]["content"] is None
        assert "tool_calls" in data["choices"][0]["message"]
        assert len(data["choices"][0]["message"]["tool_calls"]) == 1
        assert (
            data["choices"][0]["message"]["tool_calls"][0]["function"]["name"]
            == "Structure"
        )
        assert data["choices"][0]["finish_reason"] == "tool_calls"

        # Verify the function arguments are valid JSON
        args = json.loads(
            data["choices"][0]["message"]["tool_calls"][0]["function"][
                "arguments"
            ]
        )
        assert "tldr" in args
        assert "motivation" in args
        assert "method" in args
        assert "result" in args
        assert "conclusion" in args
        assert "relevance" in args

    def test_create_batch(self, openai_mock_server, openai_base_url):
        """Test batch creation endpoint."""
        response = requests.post(
            f"{openai_base_url}v1/batches",
            json={
                "input_file_id": "file-test123",
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
                "metadata": {"test": "batch"},
            },
            headers={"Authorization": "Bearer test-key"},
        )

        assert response.status_code == 200
        data = response.json()

        assert "id" in data
        assert data["object"] == "batch"
        assert data["endpoint"] == "/v1/chat/completions"
        assert data["input_file_id"] == "file-test123"
        assert data["completion_window"] == "24h"
        assert data["status"] == "validating"
        assert data["metadata"]["test"] == "batch"

    def test_list_batches(self, openai_mock_server, openai_base_url):
        """Test batch listing endpoint."""
        # First create a batch
        create_response = requests.post(
            f"{openai_base_url}v1/batches",
            json={
                "input_file_id": "file-test123",
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
            },
            headers={"Authorization": "Bearer test-key"},
        )
        assert create_response.status_code == 200

        # Then list batches
        response = requests.get(
            f"{openai_base_url}v1/batches",
            headers={"Authorization": "Bearer test-key"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["object"] == "list"
        assert len(data["data"]) >= 1
        assert data["data"][0]["object"] == "batch"

    def test_batch_status_update_via_server_method(
        self, openai_mock_server, openai_base_url
    ):
        """Test batch status update functionality through server method."""
        # Create a batch
        create_response = requests.post(
            f"{openai_base_url}v1/batches",
            json={
                "input_file_id": "file-test123",
                "endpoint": "/v1/chat/completions",
                "completion_window": "24h",
            },
            headers={"Authorization": "Bearer test-key"},
        )
        assert create_response.status_code == 200
        batch_id = create_response.json()["id"]

        # Update batch status using the mock server method
        openai_mock_server.update_batch_status(
            batch_id,
            "completed",
            output_file_id="file-output123",
            completed_at=1234567890,
        )

        # Verify the batch was updated in the internal state
        assert batch_id in openai_mock_server.batch_jobs
        batch_data = openai_mock_server.batch_jobs[batch_id]
        assert batch_data["status"] == "completed"
        assert batch_data["output_file_id"] == "file-output123"
        assert batch_data["completed_at"] == 1234567890

    def test_relevance_override_initialization(
        self, openai_mock_server_with_relevance
    ):
        """Test that relevance override can be set during initialization."""
        # Test with different relevance values
        for relevance in ["Must", "High", "Medium", "Low", "Irrelevant"]:
            mock_server = openai_mock_server_with_relevance(relevance)
            assert mock_server.get_relevance_override() == relevance

        # Test with None (should use default)
        mock_server = openai_mock_server_with_relevance(None)
        assert mock_server.get_relevance_override() is None

    def test_relevance_override_dynamic_setting(
        self, openai_mock_server, openai_base_url
    ):
        """Test that relevance can be changed dynamically during tests."""
        # Start with default relevance
        assert openai_mock_server.get_relevance_override() is None

        # Test different relevance values
        for relevance in ["Must", "High", "Medium", "Low", "Irrelevant"]:
            openai_mock_server.set_relevance_override(relevance)
            assert openai_mock_server.get_relevance_override() == relevance

            # Make a request and verify the relevance in response
            response = requests.post(
                f"{openai_base_url}v1/chat/completions",
                json={
                    "model": "gpt-4",
                    "messages": [
                        {"role": "user", "content": "Analyze this paper"}
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

            assert response.status_code == 200
            data = response.json()

            # Extract relevance from function arguments
            args = json.loads(
                data["choices"][0]["message"]["tool_calls"][0]["function"][
                    "arguments"
                ]
            )
            assert args["relevance"] == relevance

    def test_relevance_override_reset(
        self, openai_mock_server, openai_base_url
    ):
        """Test that relevance can be reset to None (default behavior)."""
        # Set a specific relevance
        openai_mock_server.set_relevance_override("Low")
        assert openai_mock_server.get_relevance_override() == "Low"

        # Reset to None
        openai_mock_server.set_relevance_override(None)
        assert openai_mock_server.get_relevance_override() is None

        # Verify it uses default "High" when None
        response = requests.post(
            f"{openai_base_url}v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Analyze this paper"}],
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

        assert response.status_code == 200
        data = response.json()

        args = json.loads(
            data["choices"][0]["message"]["tool_calls"][0]["function"][
                "arguments"
            ]
        )
        assert args["relevance"] == "High"  # Default when None

    def test_relevance_override_without_function_calling(
        self, openai_mock_server, openai_base_url
    ):
        """Test that relevance override doesn't affect non-function-calling requests."""
        # Set relevance override
        openai_mock_server.set_relevance_override("Low")

        # Make a regular chat completion request (no function calling)
        response = requests.post(
            f"{openai_base_url}v1/chat/completions",
            json={
                "model": "gpt-4",
                "messages": [{"role": "user", "content": "Hello, world!"}],
            },
            headers={"Authorization": "Bearer test-key"},
        )

        assert response.status_code == 200
        data = response.json()

        # Should return regular text response, not function calling
        assert data["choices"][0]["message"]["content"] is not None
        assert data["choices"][0]["finish_reason"] == "stop"
        # No tool_calls should be present
        assert "tool_calls" not in data["choices"][0]["message"]
