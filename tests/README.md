# OpenAI Mock Server for Testing

This directory contains a comprehensive mock OpenAI API server implemented using `pytest-httpserver` for testing purposes.

## Overview

The mock server provides realistic simulation of OpenAI's API endpoints without requiring actual API calls or incurring costs. It's defined in `conftest.py` and can be used across all test files.

### Migration Note

The AI enhancement features have been migrated from `ai/enhance.py` to the batch processing approach:
- `ai/submit_batch.py` - Submits batch jobs to OpenAI
- `ai/process_batch.py` - Processes batch results with filtering logic

### Workflow Timing

The system now uses a two-stage workflow:
1. **Crawl & Submit** (18:00 KST daily) - Crawls papers and submits batch jobs
2. **Process & Convert** (19:00 KST and 07:00 KST daily) - Processes batch results and converts to markdown

The processing workflow runs every 12 hours to handle batch jobs that may take time to complete.

## Features

### 🎯 **Supported Endpoints**

1. **Chat Completions** (`POST /v1/chat/completions`)
   - Basic text responses
   - Function/tool calling with structured output
   - Proper OpenAI response format

2. **Batch Operations**
   - `POST /v1/batches` - Create batch jobs
   - `GET /v1/batches` - List all batches
   - Batch status management

### 🔧 **Key Capabilities**

- **Realistic Responses**: Mimics actual OpenAI API response structure
- **Function Calling**: Supports structured output via tool/function calls
- **Batch Management**: Full batch lifecycle simulation
- **Error Handling**: Proper HTTP status codes and error responses
- **State Management**: Maintains batch state for testing workflows

## Usage

### Basic Setup

```python
def test_my_feature(openai_mock_server, openai_base_url):
    """Test using the mock OpenAI server."""
    response = requests.post(
        f"{openai_base_url}v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}]
        },
        headers={"Authorization": "Bearer test-key"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["model"] == "gpt-4"
```

### Function Calling

```python
def test_function_calling(openai_mock_server, openai_base_url):
    """Test function calling with structured output."""
    response = requests.post(
        f"{openai_base_url}v1/chat/completions",
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Analyze this"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "Structure",
                        "description": "Structure the analysis"
                    }
                }
            ]
        },
        headers={"Authorization": "Bearer test-key"}
    )
    
    data = response.json()
    assert data["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "Structure"
```

### Batch Operations

```python
def test_batch_operations(openai_mock_server, openai_base_url):
    """Test batch creation and management."""
    # Create a batch
    create_response = requests.post(
        f"{openai_base_url}v1/batches",
        json={
            "input_file_id": "file-123",
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h"
        },
        headers={"Authorization": "Bearer test-key"}
    )
    
    batch_id = create_response.json()["id"]
    
    # Update batch status programmatically
    openai_mock_server.update_batch_status(batch_id, "completed")
    
    # List batches
    list_response = requests.get(
        f"{openai_base_url}v1/batches",
        headers={"Authorization": "Bearer test-key"}
    )
    
    assert len(list_response.json()["data"]) >= 1
```

### Relevance Control

```python
def test_relevance_control(openai_mock_server, openai_base_url):
    """Test controlling relevance values in function calling responses."""
    
    # Set specific relevance for testing
    openai_mock_server.set_relevance_override("Low")
    
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
                        "description": "Structure the analysis"
                    }
                }
            ]
        },
        headers={"Authorization": "Bearer test-key"}
    )
    
    data = response.json()
    args = json.loads(
        data["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    )
    assert args["relevance"] == "Low"  # Controlled relevance value
```

### Relevance Control with Factory Fixture

```python
def test_relevance_factory(openai_mock_server_with_relevance, openai_base_url):
    """Test creating mock servers with predefined relevance values."""
    
    # Create server with specific relevance
    mock_server = openai_mock_server_with_relevance("Irrelevant")
    
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
                        "description": "Structure the analysis"
                    }
                }
            ]
        },
        headers={"Authorization": "Bearer test-key"}
    )
    
    data = response.json()
    args = json.loads(
        data["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"]
    )
    assert args["relevance"] == "Irrelevant"
```

## Available Fixtures

### `httpserver`
The base HTTP server instance from `pytest-httpserver`.

### `openai_mock_server`
The configured OpenAI mock server with all endpoints set up.

### `openai_mock_server_with_relevance`
A factory fixture that creates mock servers with configurable relevance values.

### `openai_base_url`
The base URL for making requests to the mock server.

## Mock Server API

### OpenAIMockServer Class

The `OpenAIMockServer` class provides:

```python
class OpenAIMockServer:
    def update_batch_status(self, batch_id: str, status: str, **kwargs):
        """Update batch status for testing purposes."""
        
    def set_relevance_override(self, relevance: str | None):
        """Set the relevance override for function calling responses."""
        
    def get_relevance_override(self) -> str | None:
        """Get the current relevance override value."""
        
    @property 
    def batch_jobs(self) -> Dict[str, Dict[str, Any]]:
        """Access to internal batch state."""
```

## Response Examples

### Chat Completion Response

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "This is a mock response from the OpenAI API."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 100,
    "completion_tokens": 50,
    "total_tokens": 150
  }
}
```

### Function Calling Response

```json
{
  "id": "chatcmpl-abc123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_abc123",
            "type": "function",
            "function": {
              "name": "Structure",
              "arguments": "{\"tldr\":\"Mock summary\",\"relevance\":\"High\"}"
            }
          }
        ]
      },
      "finish_reason": "tool_calls"
    }
  ]
}
```

### Batch Creation Response

```json
{
  "id": "batch_abc123",
  "object": "batch",
  "endpoint": "/v1/chat/completions",
  "input_file_id": "file-123",
  "completion_window": "24h",
  "status": "validating",
  "created_at": 1234567890,
  "metadata": {}
}
```

## Running Tests

```bash
# Run all tests
uv run pytest tests/unit/ -v

# Run only mock server tests
uv run pytest tests/unit/test_openai_mock_server.py -v

# Run with coverage
uv run pytest tests/unit/ --cov=tests --cov-report=html
```

## Benefits

- ✅ **No API Costs**: Test without spending money on API calls
- ✅ **Fast Execution**: No network latency or rate limits
- ✅ **Deterministic**: Consistent responses for reliable testing
- ✅ **Offline Testing**: Works without internet connection
- ✅ **Custom Scenarios**: Easy to simulate edge cases and errors
- ✅ **Relevance Control**: Test different relevance scenarios for filtering logic

## Future Enhancements

The mock server can be extended to support:
- File upload/download endpoints
- Assistant API endpoints
- Embeddings endpoints
- Image generation endpoints
- Streaming responses
- Rate limiting simulation
- Custom error scenarios
- Dynamic content generation based on input
- Response timing simulation