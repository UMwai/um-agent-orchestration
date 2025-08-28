"""
Integration example for CLI Process Manager with the provider system.

This example demonstrates how to use the CLI Process Manager with the existing
provider configuration and routing system.
"""

import asyncio
import logging

from orchestrator.cli_manager import (
    CLIProcessManager,
    ProcessLimitError,
    ProcessPoolError,
    ProcessTimeoutError,
    ResourceLimits,
)
from orchestrator.settings import load_settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedProviderCLI:
    """
    Enhanced CLI provider that uses the CLI Process Manager for better
    process lifecycle management, resource control, and monitoring.
    """

    def __init__(self, max_processes: int = 20, idle_timeout: int = 300):
        """
        Initialize the enhanced CLI provider.

        Args:
            max_processes: Maximum number of concurrent CLI processes
            idle_timeout: Timeout in seconds for idle process cleanup
        """
        self.manager = CLIProcessManager(
            max_processes=max_processes,
            idle_timeout=idle_timeout,
            resource_limits=ResourceLimits(
                max_memory_mb=2048,  # 2GB per process
                max_cpu_percent=80.0,
                max_file_descriptors=1024,
                max_execution_time=300,  # 5 minutes
            ),
            enable_monitoring=True,
        )
        self.settings = load_settings()

        # Process pool for different providers
        self.provider_pools = {}

        logger.info("Enhanced Provider CLI initialized")

    async def start(self):
        """Start the CLI manager and monitoring."""
        await self.manager.start_monitoring()
        logger.info("CLI Process Manager started")

    async def shutdown(self):
        """Shutdown the CLI manager gracefully."""
        await self.manager.shutdown()
        logger.info("CLI Process Manager shutdown complete")

    async def call_provider_with_session(
        self,
        provider_name: str,
        prompt: str,
        cwd: str | None = None,
        timeout: int | None = None,
        reuse_session: bool = True,
    ) -> tuple[str, str]:
        """
        Call a provider with session management for improved performance.

        Args:
            provider_name: Name of the provider (e.g., 'claude_cli')
            prompt: The prompt to send
            cwd: Working directory
            timeout: Command timeout in seconds
            reuse_session: Whether to reuse existing session process

        Returns:
            Tuple of (stdout, stderr)
        """
        if provider_name not in self.settings.providers:
            raise ValueError(f"Provider {provider_name} not found in configuration")

        cfg = self.settings.providers[provider_name]

        # Get or create process for this provider
        process_id = None
        if reuse_session and provider_name in self.provider_pools:
            # Try to reuse existing session
            existing_processes = self.manager.list_processes(provider_name=provider_name)
            if existing_processes:
                # Use the most recently accessed process
                process_info = max(existing_processes, key=lambda p: p.last_accessed)
                process_id = process_info.id
                logger.debug(f"Reusing existing session {process_id} for {provider_name}")

        if not process_id:
            # Create new process
            try:
                session_mode = cfg.mode == "interactive"
                process_id = await self.manager.spawn_process(
                    provider_name=provider_name, cfg=cfg, cwd=cwd, session_mode=session_mode
                )

                if reuse_session:
                    self.provider_pools[provider_name] = process_id

                logger.info(
                    f"Created new {'session' if session_mode else 'process'} {process_id} for {provider_name}"
                )

            except ProcessLimitError:
                logger.warning("Process limit reached, cleaning up idle processes")
                # Force cleanup and retry once
                await self.manager._cleanup_idle_processes()

                process_id = await self.manager.spawn_process(
                    provider_name=provider_name,
                    cfg=cfg,
                    cwd=cwd,
                    session_mode=cfg.mode == "interactive",
                )

        # Send command to process
        try:
            stdout, stderr = await self.manager.send_command(
                process_id=process_id, command=prompt, timeout=timeout
            )

            logger.debug(f"Command sent to {process_id}, got {len(stdout)} bytes output")
            return stdout, stderr

        except ProcessTimeoutError:
            logger.error(f"Command timed out for provider {provider_name}")
            # Terminate the problematic process
            await self.manager.terminate_process(process_id, force=True)
            if provider_name in self.provider_pools:
                del self.provider_pools[provider_name]
            raise

        except ProcessPoolError as e:
            logger.error(f"Process error for provider {provider_name}: {e}")
            raise

    async def call_provider_oneshot(
        self, provider_name: str, prompt: str, cwd: str | None = None, timeout: int | None = None
    ) -> tuple[str, str]:
        """
        Call a provider with one-shot execution (no session reuse).

        Args:
            provider_name: Name of the provider
            prompt: The prompt to send
            cwd: Working directory
            timeout: Command timeout in seconds

        Returns:
            Tuple of (stdout, stderr)
        """
        return await self.call_provider_with_session(
            provider_name=provider_name,
            prompt=prompt,
            cwd=cwd,
            timeout=timeout,
            reuse_session=False,
        )

    async def get_provider_health(self, provider_name: str | None = None) -> dict:
        """
        Get health status for providers.

        Args:
            provider_name: Specific provider to check, or all if None

        Returns:
            Health status dictionary
        """
        if provider_name:
            processes = self.manager.list_processes(provider_name=provider_name)
            if processes:
                return await self.manager.health_check(processes[0].id)
            else:
                return {"error": f"No processes found for provider {provider_name}"}
        else:
            return await self.manager.health_check()

    async def cleanup_provider(self, provider_name: str) -> int:
        """
        Clean up all processes for a specific provider.

        Args:
            provider_name: Name of the provider to clean up

        Returns:
            Number of processes terminated
        """
        processes = self.manager.list_processes(provider_name=provider_name)
        count = 0

        for process_info in processes:
            success = await self.manager.terminate_process(process_info.id)
            if success:
                count += 1

        if provider_name in self.provider_pools:
            del self.provider_pools[provider_name]

        logger.info(f"Cleaned up {count} processes for provider {provider_name}")
        return count


async def example_basic_usage():
    """Basic usage example."""
    print("\n=== Basic Usage Example ===")

    provider = EnhancedProviderCLI(max_processes=5, idle_timeout=60)
    await provider.start()

    try:
        # Call Claude CLI (using echo for demo)
        print("Calling Claude CLI...")
        stdout, stderr = await provider.call_provider_with_session(
            provider_name="claude_cli",
            prompt="Hello, Claude! Please write a simple Python function.",
            timeout=30,
        )
        print(f"Claude response: {stdout[:100]}...")

        # Call Codex CLI
        print("\nCalling Codex CLI...")
        stdout, stderr = await provider.call_provider_with_session(
            provider_name="codex_cli",
            prompt="def fibonacci(n): # Complete this function",
            timeout=30,
        )
        print(f"Codex response: {stdout[:100]}...")

        # Get health status
        print("\nHealth Status:")
        health = await provider.get_provider_health()
        print(f"Total processes: {health['total_processes']}")
        print(f"Alive processes: {health['alive_processes']}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await provider.shutdown()


async def example_session_reuse():
    """Example demonstrating session reuse for better performance."""
    print("\n=== Session Reuse Example ===")

    provider = EnhancedProviderCLI()
    await provider.start()

    try:
        # Multiple calls to the same provider should reuse the session
        prompts = [
            "What is the capital of France?",
            "What is 2 + 2?",
            "Write a hello world in Python",
            "Explain recursion briefly",
        ]

        print("Making multiple calls to Claude (session reuse enabled)...")
        for i, prompt in enumerate(prompts, 1):
            stdout, stderr = await provider.call_provider_with_session(
                provider_name="claude_cli", prompt=prompt, reuse_session=True
            )
            print(f"Call {i}: {stdout[:50]}...")

        # Check how many processes are actually running
        health = await provider.get_provider_health("claude_cli")
        claude_processes = [p for p in health["processes"] if p["provider"] == "claude_cli"]
        print(f"\nNumber of Claude processes after 4 calls: {len(claude_processes)}")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await provider.shutdown()


async def example_resource_monitoring():
    """Example demonstrating resource monitoring and limits."""
    print("\n=== Resource Monitoring Example ===")

    # Configure with lower limits for demonstration
    provider = EnhancedProviderCLI(max_processes=3, idle_timeout=30)
    await provider.start()

    try:
        # Spawn processes up to the limit
        providers_to_test = ["claude_cli", "codex_cli", "gemini_cli"]

        print("Spawning processes up to limit...")
        for provider_name in providers_to_test:
            try:
                stdout, stderr = await provider.call_provider_with_session(
                    provider_name=provider_name, prompt="Test prompt", reuse_session=True
                )
                print(f"✓ {provider_name} process created")
            except ProcessLimitError:
                print(f"✗ {provider_name} failed: process limit reached")
            except Exception as e:
                print(f"✗ {provider_name} failed: {e}")

        # Try to exceed the limit
        try:
            await provider.call_provider_with_session(
                provider_name="cursor_cli", prompt="This should fail", reuse_session=False
            )
        except ProcessLimitError:
            print("✓ Process limit correctly enforced")

        # Show detailed health information
        print("\nDetailed Health Status:")
        health = await provider.get_provider_health()
        for process in health["processes"]:
            print(
                f"  Process {process['id'][:8]}... "
                f"({process['provider']}) - "
                f"Alive: {process['alive']}, "
                f"Idle: {process['idle_time']:.1f}s"
            )

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await provider.shutdown()


async def example_error_handling():
    """Example demonstrating error handling and recovery."""
    print("\n=== Error Handling Example ===")

    provider = EnhancedProviderCLI()
    await provider.start()

    try:
        # Test timeout handling
        print("Testing timeout handling...")
        try:
            # This would timeout with a real long-running command
            await provider.call_provider_with_session(
                provider_name="claude_cli",
                prompt="Long running task simulation",
                timeout=1,  # Very short timeout for demo
            )
        except ProcessTimeoutError:
            print("✓ Timeout correctly handled")
        except Exception as e:
            print(f"! Unexpected error: {e}")

        # Test provider cleanup after error
        print("\nCleaning up claude_cli processes...")
        count = await provider.cleanup_provider("claude_cli")
        print(f"✓ Cleaned up {count} processes")

        # Test recovery - should work after cleanup
        print("\nTesting recovery after cleanup...")
        stdout, stderr = await provider.call_provider_with_session(
            provider_name="claude_cli", prompt="Recovery test", reuse_session=True
        )
        print("✓ Successfully recovered and created new process")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        await provider.shutdown()


async def main():
    """Run all examples."""
    print("CLI Process Manager Integration Examples")
    print("=" * 50)

    # Note: These examples use the configured providers from config.yaml
    # In a real environment, make sure the CLI tools (claude, codex, etc.) are installed

    try:
        await example_basic_usage()
        await asyncio.sleep(1)

        await example_session_reuse()
        await asyncio.sleep(1)

        await example_resource_monitoring()
        await asyncio.sleep(1)

        await example_error_handling()

    except Exception as e:
        print(f"Example failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
