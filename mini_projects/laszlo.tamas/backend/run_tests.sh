#!/bin/bash
# Test runner script for Knowledge Router
# Provides different test modes with appropriate coverage settings

set -e

MODE="${1:-quick}"

show_help() {
    cat << EOF
Knowledge Router Test Runner
=============================

Usage: ./run_tests.sh [mode]

Modes:
  quick       Run tests without OpenAI, no coverage threshold (default)
  excel       Run only Excel integration tests
  integration Run all integration tests
  full        Run ALL tests with 70% coverage threshold
  unit        Run only unit tests (fast)

Examples:
  ./run_tests.sh                    # Quick run (no OpenAI, no threshold)
  ./run_tests.sh excel              # Excel tests only
  ./run_tests.sh full               # Full suite with coverage check

EOF
}

# Base docker-compose command
DOCKER_CMD="docker-compose exec -T -e RUN_OPENAI_TESTS=N backend"

case "$MODE" in
    quick)
        echo "🚀 Quick test run (no OpenAI, no coverage threshold)"
        $DOCKER_CMD pytest tests/ -v
        ;;
    
    excel)
        echo "📊 Excel integration tests"
        $DOCKER_CMD pytest tests/integration/test_excel_integration.py -v
        ;;
    
    integration)
        echo "🔗 Integration tests"
        $DOCKER_CMD pytest tests/integration/ -v -m integration
        ;;
    
    unit)
        echo "⚡ Unit tests (fast)"
        $DOCKER_CMD pytest tests/unit/ -v -m unit
        ;;
    
    full)
        echo "🎯 FULL test suite with 70% coverage threshold"
        echo "   This will test ALL code and enforce quality standards"
        
        read -p "Run OpenAI tests? (y/N): " openai_choice
        OPENAI_FLAG="N"
        if [[ "$openai_choice" =~ ^[Yy]$ ]]; then
            OPENAI_FLAG="Y"
        fi
        
        docker-compose exec -T -e RUN_OPENAI_TESTS=$OPENAI_FLAG backend pytest tests/ -v --cov-fail-under=70
        ;;
    
    help|--help|-h)
        show_help
        exit 0
        ;;
    
    *)
        echo "❌ Unknown mode: $MODE"
        echo "   Run with 'help' to see available modes"
        exit 1
        ;;
esac

# Check exit code
if [ $? -eq 0 ]; then
    echo -e "\n✅ Tests passed!"
else
    echo -e "\n❌ Tests failed!"
    exit 1
fi
