#!/usr/bin/env python3
"""
Comprehensive test runner for Kometa-AI.

This script handles all test-related operations:
1. Setting up the test environment
2. Running tests with various options
3. Generating coverage reports
4. Running specific test modules or classes

Usage:
    python run_tests.py [options]

Options:
    --setup             Run setup only without tests
    --all               Run all tests (default)
    --unit              Run unit tests only
    --integration       Run integration tests only
    --module MODULE     Run tests in the specified module only (e.g. test_parser)
    --coverage          Generate coverage report
    --verbose           Enable verbose output
    --ci                Run in CI mode (skip production tests)
    --no-setup          Skip setup and run tests directly
"""

import os
import sys
import argparse
import subprocess
import shutil
from pathlib import Path

# Configure environment
os.environ["PYTHONPATH"] = os.getcwd()
os.environ["PYTHONUNBUFFERED"] = "1"

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Comprehensive test runner for Kometa-AI")
    parser.add_argument("--setup", action="store_true", help="Run setup only without tests")
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--module", type=str, help="Run tests in the specified module only (e.g. test_parser)")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--ci", action="store_true", help="Run in CI mode (skip production tests)")
    parser.add_argument("--no-setup", action="store_true", help="Skip setup and run tests directly")
    
    args = parser.parse_args()
    
    # If no test filter is specified, default to --all
    if not (args.all or args.unit or args.integration or args.module):
        args.all = True
    
    return args

def run_setup():
    """Run CI setup script."""
    print("Running setup...")
    setup_cmd = [sys.executable, "ci_setup.py"]
    
    try:
        result = subprocess.run(setup_cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Setup failed with error: {e}")
        return False

def get_test_command(args):
    """Build the pytest command based on arguments."""
    cmd = [sys.executable, "-m", "pytest"]
    
    # Add test selection
    if args.module:
        # Handle both with and without .py extension
        module_name = args.module
        if module_name.endswith(".py"):
            module_name = module_name[:-3]
        cmd.append(f"tests/{module_name}.py")
    elif args.unit:
        # Exclude integration tests (modify this pattern according to your naming conventions)
        cmd.extend(["-k", "not integration"])
    elif args.integration:
        # Run only integration tests
        cmd.extend(["-k", "integration"])
    # args.all is default, so we don't need to modify the command for it
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-v")  # Default to some verbosity
    
    # Show output
    cmd.append("-s")
    
    # Add coverage if requested
    if args.coverage:
        cmd = [sys.executable, "-m", "coverage", "run", "--source=kometa_ai", "-m", "pytest"] + cmd[3:]
    
    return cmd

def run_tests(args):
    """Run the tests with the specified options."""
    # Set environment variables
    if args.ci:
        os.environ["CI"] = "true"
        os.environ["SKIP_PRODUCTION_TESTS"] = "true"
    
    # Build test command
    cmd = get_test_command(args)
    
    print(f"Running: {' '.join(cmd)}")
    try:
        test_result = subprocess.run(cmd, check=False)
        return test_result.returncode
    except subprocess.CalledProcessError as e:
        print(f"Tests failed with error: {e}")
        return e.returncode

def generate_coverage_report():
    """Generate coverage reports."""
    print("Generating coverage reports...")
    
    try:
        # Generate XML report for CI systems
        subprocess.run([sys.executable, "-m", "coverage", "xml"], check=True)
        
        # Generate HTML report for local viewing
        subprocess.run([sys.executable, "-m", "coverage", "html"], check=True)
        
        # Print coverage report to console
        subprocess.run([sys.executable, "-m", "coverage", "report"], check=True)
        
        # Show where the HTML report is
        html_dir = os.path.join(os.getcwd(), "htmlcov")
        if os.path.exists(html_dir):
            print(f"HTML coverage report available at: {html_dir}/index.html")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"Coverage report generation failed: {e}")
        return False

def main():
    """Main function."""
    args = parse_args()
    
    print("Kometa-AI Test Runner")
    print("====================")
    
    if not args.no_setup:
        setup_success = run_setup()
        if not setup_success:
            print("⚠️ Setup completed with warnings/errors")
        else:
            print("✅ Setup completed successfully")
        
        if args.setup:
            print("Setup-only mode, exiting...")
            return 0
    
    test_result = run_tests(args)
    
    # Generate coverage report if requested and tests passed
    if args.coverage and test_result == 0:
        coverage_success = generate_coverage_report()
        if not coverage_success:
            print("⚠️ Coverage report generation failed")
        else:
            print("✅ Coverage report generated successfully")
    
    # Return the test result code
    return test_result

if __name__ == "__main__":
    sys.exit(main())