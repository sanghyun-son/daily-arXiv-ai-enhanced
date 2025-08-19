#!/bin/bash

# Test runner script for the batch processing integration tests

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

# Function to run all tests
run_all_tests() {
    print_status "🧪 Running OpenAI Batch API Integration Tests"
    echo "============================================================"
    
    # Check if we're in the right directory
    if [ ! -d "tests" ]; then
        print_error "❌ Error: tests directory not found. Please run from project root."
        exit 1
    fi
    
    # Check if pytest is available
    if ! command -v pytest &> /dev/null; then
        print_error "❌ Error: pytest not found. Please install test dependencies:"
        print_error "   uv add --dev pytest pytest-cov pytest-mock"
        exit 1
    fi
    
    # Run pytest
    if pytest tests/integration/ -v --tb=short; then
        print_success "\n✅ All tests passed!"
        return 0
    else
        print_error "\n❌ Tests failed with exit code: $?"
        return 1
    fi
}

# Function to run specific test file
run_specific_test() {
    local test_file="$1"
    print_status "🧪 Running specific test: $test_file"
    echo "============================================================"
    
    local test_path="tests/integration/$test_file"
    if [ ! -f "$test_path" ]; then
        print_error "❌ Error: Test file $test_path not found."
        exit 1
    fi
    
    if pytest "$test_path" -v --tb=short; then
        print_success "\n✅ Test $test_file passed!"
        return 0
    else
        print_error "\n❌ Test $test_file failed with exit code: $?"
        return 1
    fi
}

# Function to run tests with coverage
run_tests_with_coverage() {
    print_status "🧪 Running tests with coverage report"
    echo "============================================================"
    
    if [ ! -d "tests" ]; then
        print_error "❌ Error: tests directory not found. Please run from project root."
        exit 1
    fi
    
    if pytest tests/integration/ -v --cov=ai --cov-report=term-missing --tb=short; then
        print_success "\n✅ Coverage report generated successfully!"
        return 0
    else
        print_error "\n❌ Coverage test failed with exit code: $?"
        return 1
    fi
}

# Function to show help
show_help() {
    echo "Usage: $0 [OPTION] [TEST_FILE]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -c, --coverage      Run tests with coverage report"
    echo "  TEST_FILE           Run specific test file (e.g., test_submit_batch.py)"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run all tests"
    echo "  $0 test_submit_batch.py    # Run submit batch tests only"
    echo "  $0 test_process_batch.py   # Run process batch tests only"
    echo "  $0 --coverage        # Run all tests with coverage"
    echo ""
    echo "Test files available:"
    if [ -d "tests/integration" ]; then
        for file in tests/integration/test_*.py; do
            if [ -f "$file" ]; then
                echo "  - $(basename "$file")"
            fi
        done
    else
        echo "  No test files found"
    fi
}

# Main function
main() {
    # Check if virtual environment is activated
    if [ -z "$VIRTUAL_ENV" ] && [ -z "$CONDA_DEFAULT_ENV" ]; then
        print_warning "⚠️  Warning: No virtual environment detected."
        print_warning "   Consider activating your virtual environment first."
        echo ""
    fi
    
    # Parse command line arguments
    case "${1:-}" in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--coverage)
            run_tests_with_coverage
            ;;
        "")
            run_all_tests
            ;;
        *)
            # Check if it's a valid test file
            if [[ "$1" == test_*.py ]]; then
                run_specific_test "$1"
            else
                print_error "❌ Error: Invalid test file '$1'"
                echo ""
                show_help
                exit 1
            fi
            ;;
    esac
    
    # Check exit status
    if [ $? -eq 0 ]; then
        print_success "\n🎉 Test execution completed successfully!"
        exit 0
    else
        print_error "\n⚠️  Test execution completed with failures."
        exit 1
    fi
}

# Run main function with all arguments
main "$@"
