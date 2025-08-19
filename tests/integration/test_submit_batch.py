"""
Integration tests for submit_batch.py
"""

import os
import json
import tempfile
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add the ai directory to the path and change to it for imports
ai_dir = str(Path(__file__).parent.parent.parent / "ai")
sys.path.insert(0, ai_dir)

# Change to ai directory for imports
original_cwd = os.getcwd()
os.chdir(ai_dir)

from submit_batch import create_batch_requests, submit_batch_job

# Change back to original directory
os.chdir(original_cwd)


class TestSubmitBatch:
    """Test cases for submit_batch.py"""

    @pytest.fixture
    def sample_data(self):
        """Sample arXiv paper data for testing"""
        return [
            {
                "id": "test_paper_1",
                "title": "Test Paper 1: Machine Learning Advances",
                "summary": "This paper presents a novel approach to machine learning that improves accuracy by 15% while reducing computational complexity. The method combines deep learning with traditional statistical techniques.",
                "authors": ["Test Author 1", "Test Author 2"],
                "categories": ["cs.AI", "cs.LG"],
                "published": "2024-01-01"
            },
            {
                "id": "test_paper_2",
                "title": "Test Paper 2: Computer Vision Breakthrough",
                "summary": "We introduce a new computer vision algorithm that achieves state-of-the-art performance on ImageNet. The approach uses attention mechanisms and achieves 95% accuracy.",
                "authors": ["Test Author 3"],
                "categories": ["cs.CV"],
                "published": "2024-01-01"
            }
        ]

    @pytest.fixture
    def temp_data_file(self, sample_data):
        """Create a temporary data file for testing"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for item in sample_data:
                f.write(json.dumps(item) + '\n')
            temp_file = f.name
        
        yield temp_file
        
        # Cleanup
        if os.path.exists(temp_file):
            os.unlink(temp_file)

    def test_create_batch_requests_structure(self, sample_data):
        """Test that batch requests are created with correct structure"""
        batch_requests = create_batch_requests(sample_data, 'Chinese')
        
        assert len(batch_requests) == 2
        assert batch_requests[0]['custom_id'] == 'test_paper_1'
        assert batch_requests[1]['custom_id'] == 'test_paper_2'
        
        # Check request structure
        for request in batch_requests:
            assert 'custom_id' in request
            assert 'method' in request
            assert request['method'] == 'POST'
            assert 'url' in request
            assert request['url'] == '/v1/chat/completions'
            assert 'body' in request
            
            # Check body structure
            body = request['body']
            assert 'model' in body
            assert 'messages' in body
            assert 'functions' in body
            assert 'function_call' in body
            
            # Check messages
            messages = body['messages']
            assert len(messages) == 2
            assert messages[0]['role'] == 'system'
            assert messages[1]['role'] == 'user'
            
            # Check function call
            assert body['function_call'] == {'name': 'Structure'}

    def test_create_batch_requests_language_integration(self, sample_data):
        """Test that language is properly integrated into the prompt"""
        batch_requests = create_batch_requests(sample_data, 'English')
        
        # Check that language appears in system message
        system_message = batch_requests[0]['body']['messages'][0]['content']
        assert 'English' in system_message
        
        batch_requests_chinese = create_batch_requests(sample_data, 'Chinese')
        system_message_chinese = batch_requests_chinese[0]['body']['messages'][0]['content']
        assert 'Chinese' in system_message_chinese

    def test_create_batch_requests_content_integration(self, sample_data):
        """Test that paper content is properly integrated"""
        batch_requests = create_batch_requests(sample_data, 'Chinese')
        
        # Check that paper summary appears in user message
        user_message = batch_requests[0]['body']['messages'][1]['content']
        assert 'machine learning' in user_message.lower()
        assert 'accuracy' in user_message.lower()

    def test_create_batch_requests_function_structure(self, sample_data):
        """Test that function structure is correct"""
        batch_requests = create_batch_requests(sample_data, 'Chinese')
        
        functions = batch_requests[0]['body']['functions']
        assert len(functions) == 1
        assert functions[0]['name'] == 'Structure'
        
        # Check function parameters
        params = functions[0]['parameters']
        assert params['type'] == 'object'
        assert 'properties' in params
        assert 'required' in params
        
        # Check required fields
        required_fields = ['tldr', 'motivation', 'method', 'result', 'conclusion']
        for field in required_fields:
            assert field in params['required']
            assert field in params['properties']

    @patch('submit_batch.OpenAI')
    def test_submit_batch_job_success(self, mock_openai, temp_data_file):
        """Test successful batch job submission"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock file upload
        mock_file = Mock()
        mock_file.id = 'file_123'
        mock_client.files.create.return_value = mock_file
        
        # Mock batch job creation
        mock_batch = Mock()
        mock_batch.id = 'batch_456'
        mock_batch.status = 'validating'
        mock_batch.created_at = '2024-01-01T00:00:00Z'
        mock_client.batches.create.return_value = mock_batch
        
        # Set environment variables
        os.environ['LANGUAGE'] = 'Chinese'
        os.environ['MODEL_NAME'] = 'gpt-4o-mini'
        
        # Test submission
        batch_job_id = submit_batch_job([], 'Chinese', temp_data_file)
        
        assert batch_job_id == 'batch_456'
        
        # Verify OpenAI calls
        mock_client.files.create.assert_called_once()
        mock_client.batches.create.assert_called_once()
        
        # Check batch info file was created
        batch_info_file = temp_data_file.replace('.jsonl', '_batch_info.json')
        assert os.path.exists(batch_info_file)
        
        # Cleanup
        if os.path.exists(batch_info_file):
            os.unlink(batch_info_file)

    @patch('submit_batch.OpenAI')
    def test_submit_batch_job_file_upload_failure(self, mock_openai, temp_data_file):
        """Test batch job submission with file upload failure"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock file upload failure
        mock_client.files.create.side_effect = Exception("Upload failed")
        
        # Test submission
        with pytest.raises(Exception, match="Upload failed"):
            submit_batch_job([], 'Chinese', temp_data_file)

    @patch('submit_batch.OpenAI')
    def test_submit_batch_job_batch_creation_failure(self, mock_openai, temp_data_file):
        """Test batch job submission with batch creation failure"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock successful file upload
        mock_file = Mock()
        mock_file.id = 'file_123'
        mock_client.files.create.return_value = mock_file
        
        # Mock batch creation failure
        mock_client.batches.create.side_effect = Exception("Batch creation failed")
        
        # Test submission
        with pytest.raises(Exception, match="Batch creation failed"):
            submit_batch_job([], 'Chinese', temp_data_file)

    def test_submit_batch_job_batch_info_file_creation(self, temp_data_file):
        """Test that batch info file is created with correct structure"""
        with patch('submit_batch.OpenAI') as mock_openai:
            # Mock OpenAI client
            mock_client = Mock()
            mock_openai.return_value = mock_client
            
            # Mock file upload
            mock_file = Mock()
            mock_file.id = 'file_123'
            mock_client.files.create.return_value = mock_file
            
            # Mock batch job creation
            mock_batch = Mock()
            mock_batch.id = 'batch_456'
            mock_batch.status = 'validating'
            mock_batch.created_at = '2024-01-01T00:00:00Z'
            mock_client.batches.create.return_value = mock_batch
            
            # Set environment variables
            os.environ['LANGUAGE'] = 'Chinese'
            os.environ['MODEL_NAME'] = 'gpt-4o-mini'
            
            # Test submission
            submit_batch_job([], 'Chinese', temp_data_file)
            
            # Check batch info file
            batch_info_file = temp_data_file.replace('.jsonl', '_batch_info.json')
            assert os.path.exists(batch_info_file)
            
            with open(batch_info_file, 'r') as f:
                batch_info = json.load(f)
            
            # Check batch info structure
            assert 'batch_job_id' in batch_info
            assert 'batch_input_file_id' in batch_info
            assert 'status' in batch_info
            assert 'created_at' in batch_info
            assert 'data_file' in batch_info
            assert 'language' in batch_info
            assert 'batch_requests_file' in batch_info
            
            assert batch_info['batch_job_id'] == 'batch_456'
            assert batch_info['batch_input_file_id'] == 'file_123'
            assert batch_info['status'] == 'validating'
            assert batch_info['language'] == 'Chinese'
            
            # Cleanup
            if os.path.exists(batch_info_file):
                os.unlink(batch_info_file)

    def test_create_batch_requests_empty_data(self):
        """Test creating batch requests with empty data"""
        batch_requests = create_batch_requests([], 'Chinese')
        assert len(batch_requests) == 0

    def test_create_batch_requests_single_item(self):
        """Test creating batch requests with single item"""
        single_item = [{
            "id": "single_test",
            "title": "Single Test Paper",
            "summary": "This is a single test paper.",
            "authors": ["Single Author"],
            "categories": ["cs.AI"],
            "published": "2024-01-01"
        }]
        
        batch_requests = create_batch_requests(single_item, 'Chinese')
        assert len(batch_requests) == 1
        assert batch_requests[0]['custom_id'] == 'single_test'

    def test_create_batch_requests_duplicate_ids(self):
        """Test creating batch requests with duplicate IDs"""
        duplicate_data = [
            {
                "id": "duplicate_id",
                "title": "First Paper",
                "summary": "First paper content",
                "authors": ["Author 1"],
                "categories": ["cs.AI"],
                "published": "2024-01-01"
            },
            {
                "id": "duplicate_id",  # Same ID
                "title": "Second Paper", 
                "summary": "Second paper content",
                "authors": ["Author 2"],
                "categories": ["cs.CV"],
                "published": "2024-01-01"
            }
        ]
        
        # Should handle duplicates gracefully
        batch_requests = create_batch_requests(duplicate_data, 'Chinese')
        assert len(batch_requests) == 2
        assert batch_requests[0]['custom_id'] == 'duplicate_id'
        assert batch_requests[1]['custom_id'] == 'duplicate_id'
