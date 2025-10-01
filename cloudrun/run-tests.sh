#!/usr/bin/env bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Run tests for Cloud Run Service
test_service() {
    log_info "Running tests for Cloud Run Service..."
    cd service
    
    # Install test dependencies
    pip install -r requirements-test.txt
    
    # Run tests
    pytest test_main.py -v --cov=. --cov-report=term-missing
    
    cd ..
}

# Run tests for Cloud Run Job Worker
test_job_worker() {
    log_info "Running tests for Cloud Run Job Worker..."
    cd job_worker
    
    # Install test dependencies
    pip install -r requirements-test.txt
    
    # Run tests
    pytest test_worker.py -v --cov=. --cov-report=term-missing
    
    cd ..
}

# Main test function
main() {
    log_info "Starting Cloud Run component tests..."
    
    test_service
    test_job_worker
    
    log_info "All tests completed successfully!"
}

# Run main function
main "$@"
