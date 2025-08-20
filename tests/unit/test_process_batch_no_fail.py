"""Test the --no_fail functionality in process_batch.py."""

import json
import tempfile
import os
from unittest.mock import patch, MagicMock

import pytest


class TestProcessBatchNoFail:
    """Test that process_batch.py handles --no_fail flag correctly."""

    def test_no_fail_flag_prevents_error_exit(self):
        """Test that --no_fail flag prevents exit code 1 when batch job not found."""
        from ai.process_batch import main

        # Create a temporary data file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write('{"id": "test1", "summary": "test paper"}\n')
            data_file = f.name

        try:
            # Mock sys.argv to include --no_fail flag
            with patch(
                "sys.argv",
                ["process_batch.py", "--data", data_file, "--no_fail"],
            ):
                # Mock the process_batch_results function to return False (simulating failure)
                with patch(
                    "ai.process_batch.process_batch_results", return_value=False
                ):
                    # Mock sys.exit to capture the exit code
                    with patch("sys.exit") as mock_exit:
                        main()

                        # Should exit with code 0 (success) even though processing failed
                        mock_exit.assert_called_once_with(0)

        finally:
            # Clean up
            os.unlink(data_file)

    def test_normal_mode_exits_with_error_on_failure(self):
        """Test that normal mode exits with code 1 when batch job not found."""
        from ai.process_batch import main

        # Create a temporary data file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write('{"id": "test1", "summary": "test paper"}\n')
            data_file = f.name

        try:
            # Mock sys.argv without --no_fail flag
            with patch("sys.argv", ["process_batch.py", "--data", data_file]):
                # Mock the process_batch_results function to return False (simulating failure)
                with patch(
                    "ai.process_batch.process_batch_results", return_value=False
                ):
                    # Mock sys.exit to capture the exit code
                    with patch("sys.exit") as mock_exit:
                        main()

                        # Should exit with code 1 (error) when processing failed
                        mock_exit.assert_called_once_with(1)

        finally:
            # Clean up
            os.unlink(data_file)

    def test_success_mode_exits_with_success(self):
        """Test that both modes exit with code 0 when processing succeeds."""
        from ai.process_batch import main

        # Create a temporary data file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False
        ) as f:
            f.write('{"id": "test1", "summary": "test paper"}\n')
            data_file = f.name

        try:
            # Test with --no_fail flag
            with patch(
                "sys.argv",
                ["process_batch.py", "--data", data_file, "--no_fail"],
            ):
                with patch(
                    "ai.process_batch.process_batch_results", return_value=True
                ):
                    with patch("sys.exit") as mock_exit:
                        main()
                        mock_exit.assert_called_once_with(0)

            # Test without --no_fail flag
            with patch("sys.argv", ["process_batch.py", "--data", data_file]):
                with patch(
                    "ai.process_batch.process_batch_results", return_value=True
                ):
                    with patch("sys.exit") as mock_exit:
                        main()
                        mock_exit.assert_called_once_with(0)

        finally:
            # Clean up
            os.unlink(data_file)
