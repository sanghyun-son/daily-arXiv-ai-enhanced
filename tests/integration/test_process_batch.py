"""
Integration tests for process_batch.py
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

from process_batch import (
    check_batch_status, 
    download_batch_results, 
    parse_batch_results, 
    process_batch_results
)

# Change back to original directory
os.chdir(original_cwd)


class TestProcessBatch:
    """Test cases for process_batch.py"""

    @pytest.fixture
    def sample_batch_info(self):
        """Sample batch info for testing"""
        return {
            "batch_job_id": "batch_123",
            "batch_input_file_id": "file_456",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00Z",
            "data_file": "test_data.jsonl",
            "language": "Chinese",
            "batch_requests_file": "test_requests.jsonl"
        }

    @pytest.fixture
    def sample_batch_results(self):
        """Sample batch results for testing"""
        return [
            {
                "custom_id": "test_paper_1",
                "response": {
                    "body": {
                        "choices": [{
                            "message": {
                                "function_call": {
                                    "name": "Structure",
                                    "arguments": json.dumps({
                                        "tldr": "Test TLDR for paper 1",
                                        "motivation": "Test motivation for paper 1",
                                        "method": "Test method for paper 1",
                                        "result": "Test result for paper 1",
                                        "conclusion": "Test conclusion for paper 1"
                                    })
                                }
                            }
                        }]
                    }
                }
            },
            {
                "custom_id": "test_paper_2",
                "response": {
                    "body": {
                        "choices": [{
                            "message": {
                                "function_call": {
                                    "name": "Structure",
                                    "arguments": json.dumps({
                                        "tldr": "Test TLDR for paper 2",
                                        "motivation": "Test motivation for paper 2",
                                        "method": "Test method for paper 2",
                                        "result": "Test result for paper 2",
                                        "conclusion": "Test conclusion for paper 2"
                                    })
                                }
                            }
                        }]
                    }
                }
            }
        ]

    @pytest.fixture
    def sample_original_data(self):
        """Sample original data for testing"""
        return [
            {
                "id": "test_paper_1",
                "title": "Test Paper 1",
                "summary": "This is test paper 1",
                "authors": ["Author 1"],
                "categories": ["cs.AI"],
                "published": "2024-01-01"
            },
            {
                "id": "test_paper_2",
                "title": "Test Paper 2",
                "summary": "This is test paper 2",
                "authors": ["Author 2"],
                "categories": ["cs.CV"],
                "published": "2024-01-01"
            }
        ]

    @pytest.fixture
    def temp_files(self, sample_batch_info, sample_original_data):
        """Create temporary files for testing"""
        # Create temporary data file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for item in sample_original_data:
                f.write(json.dumps(item) + '\n')
            data_file = f.name
        
        # Create temporary batch info file
        batch_info_file = data_file.replace('.jsonl', '_batch_info.json')
        with open(batch_info_file, 'w') as f:
            json.dump(sample_batch_info, f)
        
        yield data_file, batch_info_file
        
        # Cleanup
        for file_path in [data_file, batch_info_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)

    @patch('process_batch.OpenAI')
    def test_check_batch_status_success(self, mock_openai):
        """Test successful batch status check"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock batch job
        mock_batch = Mock()
        mock_batch.id = 'batch_123'
        mock_batch.status = 'completed'
        mock_batch.created_at = '2024-01-01T00:00:00Z'
        mock_batch.completed_at = '2024-01-01T01:00:00Z'
        mock_batch.failed_at = None
        mock_batch.expired_at = None
        mock_batch.request_counts = {'total': 10, 'completed': 10, 'failed': 0}
        mock_batch.output_file_id = 'output_789'
        mock_batch.error_file_id = None
        
        mock_client.batches.retrieve.return_value = mock_batch
        
        # Test status check
        status_info = check_batch_status('batch_123')
        
        assert status_info['id'] == 'batch_123'
        assert status_info['status'] == 'completed'
        assert status_info['output_file_id'] == 'output_789'
        assert status_info['request_counts']['total'] == 10
        assert status_info['request_counts']['completed'] == 10

    @patch('process_batch.OpenAI')
    def test_check_batch_status_failed(self, mock_openai):
        """Test batch status check for failed job"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock failed batch job
        mock_batch = Mock()
        mock_batch.id = 'batch_123'
        mock_batch.status = 'failed'
        mock_batch.failed_at = '2024-01-01T01:00:00Z'
        mock_batch.error_file_id = 'error_789'
        
        mock_client.batches.retrieve.return_value = mock_batch
        
        # Test status check
        status_info = check_batch_status('batch_123')
        
        assert status_info['status'] == 'failed'
        assert status_info['error_file_id'] == 'error_789'

    @patch('process_batch.OpenAI')
    def test_download_batch_results_success(self, mock_openai):
        """Test successful batch results download"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock file content
        mock_content = b'{"test": "data"}'
        mock_client.files.content.return_value.content = mock_content
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            output_path = f.name
        
        try:
            # Test download
            success = download_batch_results('output_789', output_path)
            
            assert success is True
            assert os.path.exists(output_path)
            
            # Check file content
            with open(output_path, 'rb') as f:
                content = f.read()
            assert content == mock_content
            
        finally:
            # Cleanup
            if os.path.exists(output_path):
                os.unlink(output_path)

    @patch('process_batch.OpenAI')
    def test_download_batch_results_failure(self, mock_openai):
        """Test batch results download failure"""
        # Mock OpenAI client
        mock_client = Mock()
        mock_openai.return_value = mock_client
        
        # Mock download failure
        mock_client.files.content.side_effect = Exception("Download failed")
        
        # Test download
        success = download_batch_results('output_789', 'nonexistent_path')
        
        assert success is False

    def test_parse_batch_results_success(self, sample_batch_results):
        """Test successful batch results parsing"""
        # Create temporary results file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for result in sample_batch_results:
                f.write(json.dumps(result) + '\n')
            results_file = f.name
        
        try:
            # Test parsing
            ai_results = parse_batch_results(results_file)
            
            assert len(ai_results) == 2
            assert 'test_paper_1' in ai_results
            assert 'test_paper_2' in ai_results
            
            # Check structure of parsed results
            paper1_result = ai_results['test_paper_1']
            assert 'tldr' in paper1_result
            assert 'motivation' in paper1_result
            assert 'method' in paper1_result
            assert 'result' in paper1_result
            assert 'conclusion' in paper1_result
            
            assert paper1_result['tldr'] == 'Test TLDR for paper 1'
            assert paper1_result['motivation'] == 'Test motivation for paper 1'
            
        finally:
            # Cleanup
            if os.path.exists(results_file):
                os.unlink(results_file)

    def test_parse_batch_results_missing_function_call(self):
        """Test parsing batch results with missing function call"""
        # Create results without function call
        results_without_function = [
            {
                "custom_id": "test_paper_1",
                "response": {
                    "body": {
                        "choices": [{
                            "message": {
                                # No function_call
                            }
                        }]
                    }
                }
            }
        ]
        
        # Create temporary results file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for result in results_without_function:
                f.write(json.dumps(result) + '\n')
            results_file = f.name
        
        try:
            # Test parsing
            ai_results = parse_batch_results(results_file)
            
            assert len(ai_results) == 1
            assert 'test_paper_1' in ai_results
            
            # Should have default error values
            paper_result = ai_results['test_paper_1']
            assert paper_result['tldr'] == 'No AI result'
            assert paper_result['motivation'] == 'No AI result'
            
        finally:
            # Cleanup
            if os.path.exists(results_file):
                os.unlink(results_file)

    def test_parse_batch_results_invalid_json(self):
        """Test parsing batch results with invalid JSON in function call"""
        # Create results with invalid JSON
        results_with_invalid_json = [
            {
                "custom_id": "test_paper_1",
                "response": {
                    "body": {
                        "choices": [{
                            "message": {
                                "function_call": {
                                    "name": "Structure",
                                    "arguments": "invalid json {"
                                }
                            }
                        }]
                    }
                }
            }
        ]
        
        # Create temporary results file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            for result in results_with_invalid_json:
                f.write(json.dumps(result) + '\n')
            results_file = f.name
        
        try:
            # Test parsing
            ai_results = parse_batch_results(results_file)
            
            assert len(ai_results) == 1
            assert 'test_paper_1' in ai_results
            
            # Should have error values
            paper_result = ai_results['test_paper_1']
            assert paper_result['tldr'] == 'Error parsing result'
            assert paper_result['motivation'] == 'Error parsing result'
            
        finally:
            # Cleanup
            if os.path.exists(results_file):
                os.unlink(results_file)

    @patch('process_batch.check_batch_status')
    @patch('process_batch.download_batch_results')
    @patch('process_batch.parse_batch_results')
    def test_process_batch_results_success(self, mock_parse, mock_download, mock_check, temp_files):
        """Test successful batch processing"""
        data_file, batch_info_file = temp_files
        
        # Mock batch status check
        mock_check.return_value = {
            'status': 'completed',
            'output_file_id': 'output_789'
        }
        
        # Mock download
        mock_download.return_value = True
        
        # Mock parsing
        mock_parse.return_value = {
            'test_paper_1': {
                'tldr': 'Test TLDR',
                'motivation': 'Test motivation',
                'method': 'Test method',
                'result': 'Test result',
                'conclusion': 'Test conclusion'
            },
            'test_paper_2': {
                'tldr': 'Test TLDR 2',
                'motivation': 'Test motivation 2',
                'method': 'Test method 2',
                'result': 'Test result 2',
                'conclusion': 'Test conclusion 2'
            }
        }
        
        # Test processing
        success = process_batch_results(data_file, wait_for_completion=False)
        
        assert success is True
        
        # Check that enhanced file was created
        enhanced_file = data_file.replace('.jsonl', '_AI_enhanced_Chinese.jsonl')
        assert os.path.exists(enhanced_file)
        
        # Check enhanced file content
        with open(enhanced_file, 'r') as f:
            enhanced_data = [json.loads(line) for line in f]
        
        assert len(enhanced_data) == 2
        assert 'AI' in enhanced_data[0]
        assert enhanced_data[0]['AI']['tldr'] == 'Test TLDR'
        assert enhanced_data[1]['AI']['tldr'] == 'Test TLDR 2'
        
        # Cleanup
        if os.path.exists(enhanced_file):
            os.unlink(enhanced_file)

    @patch('process_batch.check_batch_status')
    def test_process_batch_results_not_ready(self, mock_check, temp_files):
        """Test batch processing when job is not ready"""
        data_file, batch_info_file = temp_files
        
        # Mock batch status check - not ready
        mock_check.return_value = {
            'status': 'in_progress'
        }
        
        # Test processing
        success = process_batch_results(data_file, wait_for_completion=False)
        
        assert success is False

    @patch('process_batch.check_batch_status')
    def test_process_batch_results_failed(self, mock_check, temp_files):
        """Test batch processing when job failed"""
        data_file, batch_info_file = temp_files
        
        # Mock batch status check - failed
        mock_check.return_value = {
            'status': 'failed'
        }
        
        # Test processing
        success = process_batch_results(data_file, wait_for_completion=False)
        
        assert success is False

    def test_process_batch_results_missing_batch_info(self):
        """Test batch processing with missing batch info file"""
        # Create temporary data file without batch info
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write('{"id": "test", "title": "Test"}\n')
            data_file = f.name
        
        try:
            # Test processing
            success = process_batch_results(data_file, wait_for_completion=False)
            
            assert success is False
            
        finally:
            # Cleanup
            if os.path.exists(data_file):
                os.unlink(data_file)

    @patch('process_batch.check_batch_status')
    @patch('process_batch.download_batch_results')
    def test_process_batch_results_download_failure(self, mock_download, mock_check, temp_files):
        """Test batch processing with download failure"""
        data_file, batch_info_file = temp_files
        
        # Mock batch status check
        mock_check.return_value = {
            'status': 'completed',
            'output_file_id': 'output_789'
        }
        
        # Mock download failure
        mock_download.return_value = False
        
        # Test processing
        success = process_batch_results(data_file, wait_for_completion=False)
        
        assert success is False

    def test_process_batch_results_missing_ai_results(self, temp_files):
        """Test batch processing when some papers don't have AI results"""
        data_file, batch_info_file = temp_files
        
        with patch('process_batch.check_batch_status') as mock_check:
            mock_check.return_value = {
                'status': 'completed',
                'output_file_id': 'output_789'
            }
            
            with patch('process_batch.download_batch_results') as mock_download:
                mock_download.return_value = True
                
                with patch('process_batch.parse_batch_results') as mock_parse:
                    # Only return result for one paper
                    mock_parse.return_value = {
                        'test_paper_1': {
                            'tldr': 'Test TLDR',
                            'motivation': 'Test motivation',
                            'method': 'Test method',
                            'result': 'Test result',
                            'conclusion': 'Test conclusion'
                        }
                        # Missing test_paper_2
                    }
                    
                    # Test processing
                    success = process_batch_results(data_file, wait_for_completion=False)
                    
                    assert success is True
                    
                    # Check that enhanced file was created
                    enhanced_file = data_file.replace('.jsonl', '_AI_enhanced_Chinese.jsonl')
                    assert os.path.exists(enhanced_file)
                    
                    # Check enhanced file content
                    with open(enhanced_file, 'r') as f:
                        enhanced_data = [json.loads(line) for line in f]
                    
                    assert len(enhanced_data) == 2
                    assert enhanced_data[0]['AI']['tldr'] == 'Test TLDR'
                    assert enhanced_data[1]['AI']['tldr'] == 'No AI result'  # Default for missing
                    
                    # Cleanup
                    if os.path.exists(enhanced_file):
                        os.unlink(enhanced_file)
