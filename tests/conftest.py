"""Pytest configuration and fixtures for OpenAI mock server."""

import json
import uuid
from datetime import datetime
from typing import Dict, Any

import pytest
from pytest_httpserver import HTTPServer
from werkzeug import Request, Response


class OpenAIMockServer:
    """Mock OpenAI API server with essential endpoints."""

    def __init__(
        self, httpserver: HTTPServer, relevance_override: str | None = None
    ):
        self.server = httpserver
        self.batch_jobs: Dict[str, Dict[str, Any]] = {}
        self.relevance_override = relevance_override
        self._setup_routes()

    def _setup_routes(self):
        """Setup API routes."""
        # Chat completions endpoint
        self.server.expect_request(
            "/v1/chat/completions", method="POST"
        ).respond_with_handler(self._handle_chat_completions)

        # Batch creation endpoint
        self.server.expect_request(
            "/v1/batches", method="POST"
        ).respond_with_handler(self._handle_create_batch)

        # Individual batch retrieval - use wildcard (must come before generic /v1/batches)
        self.server.expect_request(
            "/v1/batches/batch_*", method="GET"
        ).respond_with_handler(self._handle_get_batch)

        # Batch listing endpoint
        self.server.expect_request(
            "/v1/batches", method="GET"
        ).respond_with_handler(self._handle_list_batches)

    def _handle_chat_completions(self, request: Request) -> Response:
        """Handle /v1/chat/completions endpoint."""
        try:
            data = request.get_json()
            model = data.get("model", "gpt-4")
            messages = data.get("messages", [])

            # Check if this is a function calling request
            tools = data.get("tools", [])
            tool_choice = data.get("tool_choice")

            response_data = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
                "object": "chat.completion",
                "created": int(datetime.now().timestamp()),
                "model": model,
                "choices": [],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }

            # Generate response based on whether tools are used
            if tools and any(tool.get("type") == "function" for tool in tools):
                # Function calling response
                # Use relevance override if provided, otherwise default to "High"
                relevance = (
                    self.relevance_override
                    if self.relevance_override is not None
                    else "High"
                )

                choice = {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": f"call_{uuid.uuid4().hex[:8]}",
                                "type": "function",
                                "function": {
                                    "name": "Structure",
                                    "arguments": json.dumps(
                                        {
                                            "tldr": "Mock AI-generated summary",
                                            "motivation": "Mock motivation",
                                            "method": "Mock method",
                                            "result": "Mock result",
                                            "conclusion": "Mock conclusion",
                                            "relevance": relevance,
                                        }
                                    ),
                                },
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            else:
                # Regular text response
                choice = {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "This is a mock response from the OpenAI API.",
                    },
                    "finish_reason": "stop",
                }

            response_data["choices"] = [choice]

            return Response(
                response=json.dumps(response_data),
                status=200,
                headers={"Content-Type": "application/json"},
            )

        except Exception as e:
            error_response = {
                "error": {
                    "message": f"Mock server error: {str(e)}",
                    "type": "mock_error",
                    "code": "mock_error",
                }
            }
            return Response(
                response=json.dumps(error_response),
                status=500,
                headers={"Content-Type": "application/json"},
            )

    def _handle_create_batch(self, request: Request) -> Response:
        """Handle batch creation."""
        try:
            data = request.get_json()
            batch_id = f"batch_{uuid.uuid4().hex[:8]}"

            batch_job = {
                "id": batch_id,
                "object": "batch",
                "endpoint": data.get("endpoint", "/v1/chat/completions"),
                "errors": None,
                "input_file_id": data.get("input_file_id"),
                "completion_window": data.get("completion_window", "24h"),
                "status": "validating",
                "output_file_id": None,
                "error_file_id": None,
                "created_at": int(datetime.now().timestamp()),
                "in_progress_at": None,
                "expires_at": int(datetime.now().timestamp()) + 86400,
                "completed_at": None,
                "failed_at": None,
                "expired_at": None,
                "request_counts": {"total": 0, "completed": 0, "failed": 0},
                "metadata": data.get("metadata", {}),
            }

            self.batch_jobs[batch_id] = batch_job

            return Response(
                response=json.dumps(batch_job),
                status=200,
                headers={"Content-Type": "application/json"},
            )

        except Exception as e:
            error_response = {
                "error": {
                    "message": f"Mock server error: {str(e)}",
                    "type": "mock_error",
                    "code": "mock_error",
                }
            }
            return Response(
                response=json.dumps(error_response),
                status=500,
                headers={"Content-Type": "application/json"},
            )

    def _handle_list_batches(self, request: Request) -> Response:
        """Handle batch listing."""
        try:
            response_data = {
                "object": "list",
                "data": list(self.batch_jobs.values()),
                "first_id": (
                    list(self.batch_jobs.keys())[0] if self.batch_jobs else None
                ),
                "last_id": (
                    list(self.batch_jobs.keys())[-1]
                    if self.batch_jobs
                    else None
                ),
                "has_more": False,
            }

            return Response(
                response=json.dumps(response_data),
                status=200,
                headers={"Content-Type": "application/json"},
            )

        except Exception as e:
            error_response = {
                "error": {
                    "message": f"Mock server error: {str(e)}",
                    "type": "mock_error",
                    "code": "mock_error",
                }
            }
            return Response(
                response=json.dumps(error_response),
                status=500,
                headers={"Content-Type": "application/json"},
            )

    def _handle_get_batch(self, request: Request) -> Response:
        """Handle individual batch retrieval."""
        try:
            # Extract batch_id from URL path
            batch_id = request.path.split("/")[-1]

            if batch_id in self.batch_jobs:
                return Response(
                    response=json.dumps(self.batch_jobs[batch_id]),
                    status=200,
                    headers={"Content-Type": "application/json"},
                )
            else:
                error_response = {
                    "error": {
                        "message": f"Batch {batch_id} not found",
                        "type": "invalid_request_error",
                        "code": "batch_not_found",
                    }
                }
                return Response(
                    response=json.dumps(error_response),
                    status=404,
                    headers={"Content-Type": "application/json"},
                )

        except Exception as e:
            error_response = {
                "error": {
                    "message": f"Mock server error: {str(e)}",
                    "type": "mock_error",
                    "code": "mock_error",
                }
            }
            return Response(
                response=json.dumps(error_response),
                status=500,
                headers={"Content-Type": "application/json"},
            )

    def update_batch_status(self, batch_id: str, status: str, **kwargs):
        """Update batch status for testing purposes."""
        if batch_id in self.batch_jobs:
            self.batch_jobs[batch_id]["status"] = status
            self.batch_jobs[batch_id].update(kwargs)

    def set_relevance_override(self, relevance: str | None):
        """Set the relevance override for function calling responses.

        Args:
            relevance: The relevance value to use ("Must", "High", "Medium", "Low", "Irrelevant")
                      or None to use default "High"
        """
        self.relevance_override = relevance

    def get_relevance_override(self) -> str | None:
        """Get the current relevance override value."""
        return self.relevance_override


@pytest.fixture
def httpserver():
    """Create and start HTTPServer."""
    server = HTTPServer(host="127.0.0.1", port=0)
    server.start()
    yield server
    server.stop()


@pytest.fixture
def openai_mock_server(httpserver):
    """Create OpenAI mock server."""
    mock_server = OpenAIMockServer(httpserver)
    yield mock_server


@pytest.fixture
def openai_mock_server_with_relevance(httpserver):
    """Create OpenAI mock server with configurable relevance."""

    def _create_mock_server(relevance: str | None = None):
        return OpenAIMockServer(httpserver, relevance_override=relevance)

    return _create_mock_server


@pytest.fixture
def openai_base_url(httpserver):
    """Get the base URL for the mock OpenAI server."""
    return httpserver.url_for("/")
