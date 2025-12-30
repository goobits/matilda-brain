#!/bin/bash
# Unified Test Runner for AI Library
# Runs both unit tests (free/fast) and integration tests (costs money)

set -e

# Script information
SCRIPT_NAME="$(basename "$0")"
VERSION="1.0.0"

# Default values
TEST_TYPE="unit"
COVERAGE=false
VERBOSE=false
SPECIFIC_TEST=""
MARKERS=""
FORCE_INTEGRATION=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Show help for test script
show_test_help() {
    cat << EOF
$SCRIPT_NAME - Unified Test Runner for AI Library

USAGE:
    $SCRIPT_NAME [OPTIONS] [COMMAND]

COMMANDS:
    unit           Run unit tests only (default, free, fast)
    integration    Run integration tests only (costs money, requires API keys)
    all            Run unit tests first, then integration tests
    help           Show this help message

OPTIONS:
    -c, --coverage          Generate coverage report
    -v, --verbose           Verbose test output
    -t, --test TEST         Run specific test file or pattern
    -m, --markers EXPR      Run tests matching marker expression
    -f, --force             Skip integration test confirmation
    -h, --help              Show this help message
    --version               Show version information

EXAMPLES:
    $SCRIPT_NAME                           # Run unit tests
    $SCRIPT_NAME unit --coverage           # Unit tests with coverage
    $SCRIPT_NAME integration               # Integration tests (with confirmation)
    $SCRIPT_NAME integration --force       # Integration tests (skip confirmation)
    $SCRIPT_NAME all                       # Run both unit and integration tests
    $SCRIPT_NAME --test test_api           # Run specific test file
    $SCRIPT_NAME --markers "not slow"      # Skip slow tests
    $SCRIPT_NAME unit -v -c                # Verbose unit tests with coverage

COST INFORMATION:
    • Unit tests: FREE (uses mocked API calls)
    • Integration tests: ~\$0.01-\$0.10 (uses real API calls)

REQUIREMENTS:
    • Unit tests: pytest, pytest-asyncio, pytest-cov
    • Integration tests: Valid API keys (OPENAI_API_KEY, ANTHROPIC_API_KEY, or OPENROUTER_API_KEY)

VERSION: $VERSION
EOF
}

# Show version
show_version() {
    echo "$SCRIPT_NAME version $VERSION"
}

# Check dependencies
check_dependencies() {
    if ! python3 -c "import pytest" 2>/dev/null; then
        print_color $RED "❌ pytest not found!"
        echo "Install with: pip install pytest pytest-asyncio pytest-cov"
        exit 1
    fi
}

# Check API keys for integration tests
check_api_keys() {
    local api_keys_found=0
    
    if [[ -n "$OPENAI_API_KEY" ]]; then
        print_color $GREEN "✅ OpenAI API key found"
        api_keys_found=1
    fi
    
    if [[ -n "$ANTHROPIC_API_KEY" ]]; then
        print_color $GREEN "✅ Anthropic API key found"
        api_keys_found=1
    fi
    
    if [[ -n "$OPENROUTER_API_KEY" ]]; then
        print_color $GREEN "✅ OpenRouter API key found"
        api_keys_found=1
    fi
    
    if [[ $api_keys_found -eq 0 ]]; then
        print_color $RED "❌ No API keys found!"
        echo "Set one or more of these environment variables:"
        echo "  - OPENAI_API_KEY"
        echo "  - ANTHROPIC_API_KEY"
        echo "  - OPENROUTER_API_KEY"
        echo
        echo "Example:"
        echo "  export OPENROUTER_API_KEY='your-key-here'"
        echo "  $SCRIPT_NAME integration"
        exit 1
    fi
}

# Check virtual environment
check_virtual_env() {
    if [[ -n "$VIRTUAL_ENV" ]]; then
        print_color $GREEN "✅ Virtual environment: $(basename $VIRTUAL_ENV)"
    elif [[ -d ".venv" ]]; then
        print_color $YELLOW "💡 Virtual environment available but not activated"
        echo "   Consider running: source .venv/bin/activate"
    elif [[ -d "venv" ]]; then
        print_color $YELLOW "💡 Virtual environment available but not activated"
        echo "   Consider running: source venv/bin/activate"
    fi
}

# Run unit tests
run_unit_tests() {
    print_color $BLUE "🧪 Running Unit Tests"
    print_color $BLUE "===================="
    echo
    
    # Build pytest command
    local pytest_cmd="python3 -m pytest"
    
    # Add test path or specific test
    if [[ -n "$SPECIFIC_TEST" ]]; then
        if [[ "$SPECIFIC_TEST" == *"test_"* ]]; then
            # Specific test file - add .py extension if not present
            if [[ "$SPECIFIC_TEST" != *".py" ]]; then
                SPECIFIC_TEST="${SPECIFIC_TEST}.py"
            fi
            pytest_cmd="$pytest_cmd tests/$SPECIFIC_TEST"
        else
            # Assume it's a test name pattern
            pytest_cmd="$pytest_cmd tests/ -k $SPECIFIC_TEST"
        fi
    else
        # Run all unit tests (exclude integration tests)
        pytest_cmd="$pytest_cmd tests/ -m 'not integration'"
    fi
    
    # Add markers if specified
    if [[ -n "$MARKERS" ]]; then
        pytest_cmd="$pytest_cmd -m '$MARKERS'"
    fi
    
    # Add verbose flag
    if [[ "$VERBOSE" == true ]]; then
        pytest_cmd="$pytest_cmd -v"
    fi
    
    # Add coverage if requested
    if [[ "$COVERAGE" == true ]]; then
        pytest_cmd="$pytest_cmd --cov=matilda_brain --cov-report=term-missing --cov-report=html"
        print_color $YELLOW "📊 Coverage report will be generated in htmlcov/"
        echo
    fi
    
    echo "Running: $pytest_cmd"
    echo
    
    # Execute the tests
    eval $pytest_cmd
    local exit_code=$?
    
    echo
    if [[ $exit_code -eq 0 ]]; then
        print_color $GREEN "✅ Unit tests passed!"
        if [[ "$COVERAGE" == true ]]; then
            print_color $YELLOW "📊 Coverage report: htmlcov/index.html"
        fi
    else
        print_color $RED "❌ Unit tests failed (exit code: $exit_code)"
    fi
    
    return $exit_code
}

# Run integration tests
run_integration_tests() {
    print_color $BLUE "🧪 Running Integration Tests"
    print_color $BLUE "=========================="
    echo
    
    # Check API keys
    check_api_keys
    
    echo
    print_color $YELLOW "⚠️  WARNING: These tests will make real API calls and consume credits!"
    print_color $YELLOW "💰 Estimated cost: \$0.01 - \$0.10 depending on models used"
    echo
    
    # Ask for confirmation unless forced
    if [[ "$FORCE_INTEGRATION" == false ]]; then
        read -p "Continue with integration tests? [y/N]: " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_color $YELLOW "Integration tests cancelled."
            return 0
        fi
    fi
    
    echo
    print_color $BLUE "🚀 Running integration tests..."
    echo
    
    # Build pytest command for integration tests
    local pytest_cmd="python3 -m pytest tests/test_integration.py -m integration"
    
    if [[ "$VERBOSE" == true ]]; then
        pytest_cmd="$pytest_cmd -v"
    fi
    
    echo "Running: $pytest_cmd"
    echo
    
    # Execute the tests
    eval $pytest_cmd
    local exit_code=$?
    
    echo
    if [[ $exit_code -eq 0 ]]; then
        print_color $GREEN "✅ Integration tests passed!"
    else
        print_color $RED "❌ Integration tests failed (exit code: $exit_code)"
    fi
    
    return $exit_code
}

# Parse command line arguments for test script
parse_test_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            unit)
                TEST_TYPE="unit"
                shift
                ;;
            integration)
                TEST_TYPE="integration"
                shift
                ;;
            all)
                TEST_TYPE="all"
                shift
                ;;
            help)
                show_test_help
                exit 0
                ;;
            -c|--coverage)
                COVERAGE=true
                shift
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -t|--test)
                SPECIFIC_TEST="$2"
                shift 2
                ;;
            -m|--markers)
                MARKERS="$2"
                shift 2
                ;;
            -f|--force)
                FORCE_INTEGRATION=true
                shift
                ;;
            -h|--help)
                show_test_help
                exit 0
                ;;
            --version)
                show_version
                exit 0
                ;;
            *)
                print_color $RED "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# Main execution
main() {
    print_color $BLUE "🧪 AI Library Test Runner v$VERSION"
    print_color $BLUE "================================="
    echo
    
    # Parse arguments
    parse_test_args "$@"
    
    # Check environment
    check_virtual_env
    echo
    check_dependencies
    echo
    
    # Execute based on test type
    case $TEST_TYPE in
        unit)
            run_unit_tests
            exit_code=$?
            ;;
        integration)
            run_integration_tests
            exit_code=$?
            ;;
        all)
            print_color $BLUE "Running unit tests first..."
            echo
            run_unit_tests
            unit_exit_code=$?
            
            if [[ $unit_exit_code -eq 0 ]]; then
                echo
                print_color $BLUE "Unit tests passed! Running integration tests..."
                echo
                run_integration_tests
                integration_exit_code=$?
                
                if [[ $integration_exit_code -eq 0 ]]; then
                    print_color $GREEN "🎉 All tests passed!"
                    exit_code=0
                else
                    print_color $RED "❌ Integration tests failed"
                    exit_code=$integration_exit_code
                fi
            else
                print_color $RED "❌ Unit tests failed! Skipping integration tests."
                exit_code=$unit_exit_code
            fi
            ;;
        *)
            print_color $RED "Invalid test type: $TEST_TYPE"
            exit 1
            ;;
    esac
    
    echo
    print_color $BLUE "🧪 Test run complete"
    exit $exit_code
}

# Run main function with all arguments
main "$@"