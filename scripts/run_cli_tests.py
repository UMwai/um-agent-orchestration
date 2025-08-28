#!/usr/bin/env python3
"""
CLI Integration Test Runner

Comprehensive test runner for CLI integration Phase 1 validation.
Provides organized execution of different test suites with reporting.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


class CLITestRunner:
    """Test runner for CLI integration tests."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.tests_dir = project_root / "tests"
        self.results = {}

    def run_unit_tests(self, verbose: bool = False) -> dict[str, Any]:
        """Run unit tests."""
        print("🧪 Running Unit Tests...")

        unit_test_files = [
            self.tests_dir / "unit" / "test_cli_manager.py",
            self.tests_dir / "unit" / "test_cli_session_manager.py",
            self.tests_dir / "test_cli_websocket.py",
        ]

        cmd = [
            "python",
            "-m",
            "pytest",
            *[str(f) for f in unit_test_files if f.exists()],
            "-v" if verbose else "-q",
            "--tb=short",
            "--maxfail=5",
            "--durations=10",
        ]

        return self._run_pytest_command(cmd, "unit_tests")

    def run_integration_tests(self, verbose: bool = False) -> dict[str, Any]:
        """Run integration tests."""
        print("🔗 Running Integration Tests...")

        integration_dir = self.tests_dir / "integration"
        if not integration_dir.exists():
            print(f"❌ Integration tests directory not found: {integration_dir}")
            return {"success": False, "error": "Integration tests directory not found"}

        cmd = [
            "python",
            "-m",
            "pytest",
            str(integration_dir),
            "-v" if verbose else "-q",
            "--tb=short",
            "--maxfail=3",
            "--durations=10",
            "-m",
            "integration",
        ]

        return self._run_pytest_command(cmd, "integration_tests")

    def run_performance_tests(self, verbose: bool = False) -> dict[str, Any]:
        """Run performance tests."""
        print("⚡ Running Performance Tests...")

        performance_dir = self.tests_dir / "performance"
        if not performance_dir.exists():
            print(f"❌ Performance tests directory not found: {performance_dir}")
            return {"success": False, "error": "Performance tests directory not found"}

        cmd = [
            "python",
            "-m",
            "pytest",
            str(performance_dir),
            "-v" if verbose else "-q",
            "--tb=short",
            "--maxfail=1",
            "--durations=0",
            "-m",
            "performance",
            "-s",  # Don't capture output for performance metrics
        ]

        return self._run_pytest_command(cmd, "performance_tests")

    def run_security_tests(self, verbose: bool = False) -> dict[str, Any]:
        """Run security tests."""
        print("🔒 Running Security Tests...")

        security_dir = self.tests_dir / "security"
        if not security_dir.exists():
            print(f"❌ Security tests directory not found: {security_dir}")
            return {"success": False, "error": "Security tests directory not found"}

        cmd = [
            "python",
            "-m",
            "pytest",
            str(security_dir),
            "-v" if verbose else "-q",
            "--tb=short",
            "--maxfail=2",
            "--durations=10",
            "-m",
            "security",
        ]

        return self._run_pytest_command(cmd, "security_tests")

    def run_acceptance_tests(self, verbose: bool = False) -> dict[str, Any]:
        """Run acceptance tests."""
        print("✅ Running Acceptance Tests...")

        acceptance_dir = self.tests_dir / "acceptance"
        if not acceptance_dir.exists():
            print(f"⚠️ Acceptance tests directory not found: {acceptance_dir}")
            return {"success": True, "tests_run": 0, "message": "No acceptance tests found"}

        cmd = [
            "python",
            "-m",
            "pytest",
            str(acceptance_dir),
            "-v" if verbose else "-q",
            "--tb=short",
            "--maxfail=1",
            "--durations=10",
        ]

        return self._run_pytest_command(cmd, "acceptance_tests")

    def run_quick_tests(self, verbose: bool = False) -> dict[str, Any]:
        """Run quick smoke tests."""
        print("💨 Running Quick Smoke Tests...")

        cmd = [
            "python",
            "-m",
            "pytest",
            str(self.tests_dir),
            "-v" if verbose else "-q",
            "--tb=short",
            "--maxfail=1",
            "-m",
            "not slow and not performance",
            "--durations=5",
        ]

        return self._run_pytest_command(cmd, "quick_tests")

    def run_all_tests(self, verbose: bool = False, skip_slow: bool = False) -> dict[str, Any]:
        """Run all test suites."""
        print("🚀 Running All CLI Integration Tests...")

        test_suites = [
            ("Unit Tests", self.run_unit_tests),
            ("Integration Tests", self.run_integration_tests),
            ("Security Tests", self.run_security_tests),
        ]

        if not skip_slow:
            test_suites.append(("Performance Tests", self.run_performance_tests))

        test_suites.append(("Acceptance Tests", self.run_acceptance_tests))

        all_results = {}
        overall_success = True
        total_tests = 0
        total_passed = 0
        total_failed = 0

        start_time = time.time()

        for suite_name, test_function in test_suites:
            print(f"\n{'='*60}")
            print(f"Running {suite_name}")
            print(f"{'='*60}")

            result = test_function(verbose)
            all_results[suite_name] = result

            if not result.get("success", False):
                overall_success = False

            total_tests += result.get("tests_run", 0)
            total_passed += result.get("tests_passed", 0)
            total_failed += result.get("tests_failed", 0)

            # Print suite summary
            status = "✅ PASSED" if result.get("success") else "❌ FAILED"
            print(f"\n{suite_name}: {status}")
            if "tests_run" in result:
                print(
                    f"  Tests: {result['tests_run']}, "
                    f"Passed: {result.get('tests_passed', 0)}, "
                    f"Failed: {result.get('tests_failed', 0)}"
                )

        end_time = time.time()
        total_time = end_time - start_time

        # Print overall summary
        print(f"\n{'='*60}")
        print("OVERALL TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total Time: {total_time:.2f}s")
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {total_passed}")
        print(f"Failed: {total_failed}")
        print(f"Success Rate: {(total_passed/max(1, total_tests)*100):.1f}%")
        print(f"Overall Status: {'✅ PASSED' if overall_success else '❌ FAILED'}")

        return {
            "success": overall_success,
            "total_time": total_time,
            "total_tests": total_tests,
            "total_passed": total_passed,
            "total_failed": total_failed,
            "suite_results": all_results,
        }

    def _run_pytest_command(self, cmd: list[str], test_type: str) -> dict[str, Any]:
        """Run a pytest command and parse results."""
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
            )

            end_time = time.time()
            execution_time = end_time - start_time

            # Parse pytest output
            output_lines = result.stdout.split("\n")
            error_lines = result.stderr.split("\n") if result.stderr else []

            # Extract test statistics
            stats = self._parse_pytest_output(output_lines)

            success = result.returncode == 0

            if not success:
                print(f"❌ {test_type} failed (exit code: {result.returncode})")
                if error_lines:
                    print("Error output:")
                    for line in error_lines[-10:]:  # Show last 10 lines
                        if line.strip():
                            print(f"  {line}")
            else:
                print(f"✅ {test_type} passed")

            return {
                "success": success,
                "execution_time": execution_time,
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                **stats,
            }

        except subprocess.TimeoutExpired:
            print(f"⏰ {test_type} timed out after 10 minutes")
            return {"success": False, "error": "Test execution timed out", "execution_time": 600}
        except Exception as e:
            print(f"💥 {test_type} failed with exception: {e}")
            return {"success": False, "error": str(e), "execution_time": time.time() - start_time}

    def _parse_pytest_output(self, lines: list[str]) -> dict[str, Any]:
        """Parse pytest output to extract test statistics."""
        stats = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
            "tests_error": 0,
        }

        # Look for the final summary line
        for line in lines:
            if "passed" in line or "failed" in line or "error" in line:
                # Try to extract numbers from summary line
                # Format: "X passed, Y failed, Z skipped in Xs"
                import re

                passed_match = re.search(r"(\d+) passed", line)
                failed_match = re.search(r"(\d+) failed", line)
                skipped_match = re.search(r"(\d+) skipped", line)
                error_match = re.search(r"(\d+) error", line)

                if passed_match:
                    stats["tests_passed"] = int(passed_match.group(1))
                if failed_match:
                    stats["tests_failed"] = int(failed_match.group(1))
                if skipped_match:
                    stats["tests_skipped"] = int(skipped_match.group(1))
                if error_match:
                    stats["tests_error"] = int(error_match.group(1))

                stats["tests_run"] = (
                    stats["tests_passed"] + stats["tests_failed"] + stats["tests_error"]
                )
                break

        return stats

    def generate_test_report(self, results: dict[str, Any], output_file: Path | None = None):
        """Generate test report."""
        report_lines = [
            "# CLI Integration Test Report",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            f"- Overall Status: {'✅ PASSED' if results.get('success') else '❌ FAILED'}",
            f"- Total Time: {results.get('total_time', 0):.2f}s",
            f"- Total Tests: {results.get('total_tests', 0)}",
            f"- Passed: {results.get('total_passed', 0)}",
            f"- Failed: {results.get('total_failed', 0)}",
            f"- Success Rate: {(results.get('total_passed', 0)/max(1, results.get('total_tests', 1))*100):.1f}%",
            "",
        ]

        # Add suite details
        suite_results = results.get("suite_results", {})
        if suite_results:
            report_lines.append("## Test Suite Details")
            report_lines.append("")

            for suite_name, suite_result in suite_results.items():
                status = "✅ PASSED" if suite_result.get("success") else "❌ FAILED"
                report_lines.append(f"### {suite_name}: {status}")
                report_lines.append(
                    f"- Execution Time: {suite_result.get('execution_time', 0):.2f}s"
                )
                report_lines.append(f"- Tests Run: {suite_result.get('tests_run', 0)}")
                report_lines.append(f"- Passed: {suite_result.get('tests_passed', 0)}")
                report_lines.append(f"- Failed: {suite_result.get('tests_failed', 0)}")

                if suite_result.get("error"):
                    report_lines.append(f"- Error: {suite_result['error']}")

                report_lines.append("")

        report_content = "\n".join(report_lines)

        if output_file:
            output_file.write_text(report_content)
            print(f"📊 Test report generated: {output_file}")
        else:
            print("\n" + "=" * 60)
            print("TEST REPORT")
            print("=" * 60)
            print(report_content)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run CLI Integration Tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_cli_tests.py --all                 # Run all tests
  python scripts/run_cli_tests.py --unit                # Run unit tests only
  python scripts/run_cli_tests.py --integration         # Run integration tests
  python scripts/run_cli_tests.py --performance         # Run performance tests
  python scripts/run_cli_tests.py --security            # Run security tests
  python scripts/run_cli_tests.py --quick               # Run quick smoke tests
  python scripts/run_cli_tests.py --all --skip-slow     # Run all except slow tests
  python scripts/run_cli_tests.py --all --report results.md  # Generate report
        """,
    )

    # Test suite options
    parser.add_argument("--all", action="store_true", help="Run all test suites")
    parser.add_argument("--unit", action="store_true", help="Run unit tests")
    parser.add_argument("--integration", action="store_true", help="Run integration tests")
    parser.add_argument("--performance", action="store_true", help="Run performance tests")
    parser.add_argument("--security", action="store_true", help="Run security tests")
    parser.add_argument("--acceptance", action="store_true", help="Run acceptance tests")
    parser.add_argument("--quick", action="store_true", help="Run quick smoke tests")

    # Options
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--skip-slow", action="store_true", help="Skip slow tests")
    parser.add_argument("--report", type=Path, help="Generate test report to file")

    args = parser.parse_args()

    # Determine project root
    project_root = Path(__file__).parent.parent

    # Initialize test runner
    runner = CLITestRunner(project_root)

    # Check if no test suite specified
    if not any(
        [
            args.all,
            args.unit,
            args.integration,
            args.performance,
            args.security,
            args.acceptance,
            args.quick,
        ]
    ):
        print("❌ No test suite specified. Use --help for options.")
        return 1

    # Run specified tests
    results = None

    try:
        if args.all:
            results = runner.run_all_tests(args.verbose, args.skip_slow)
        elif args.unit:
            results = runner.run_unit_tests(args.verbose)
        elif args.integration:
            results = runner.run_integration_tests(args.verbose)
        elif args.performance:
            results = runner.run_performance_tests(args.verbose)
        elif args.security:
            results = runner.run_security_tests(args.verbose)
        elif args.acceptance:
            results = runner.run_acceptance_tests(args.verbose)
        elif args.quick:
            results = runner.run_quick_tests(args.verbose)

        # Generate report if requested
        if results and args.report:
            runner.generate_test_report(results, args.report)

        # Exit with appropriate code
        return 0 if results and results.get("success") else 1

    except KeyboardInterrupt:
        print("\n⚠️ Test execution interrupted by user")
        return 130
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
