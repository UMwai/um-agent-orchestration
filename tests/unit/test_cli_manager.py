"""Legacy CLI manager tests (skipped for simplified orchestrator)."""

import pytest


pytest.skip(
    "Legacy CLI manager module is not available in the simplified orchestrator.",
    allow_module_level=True,
)


class TestResourceLimits:
    """Test ResourceLimits dataclass."""

    def test_default_values(self):
        """Test default resource limit values."""
        limits = ResourceLimits()
        assert limits.max_memory_mb == 2048
        assert limits.max_cpu_percent == 80.0
        assert limits.max_file_descriptors == 1024
        assert limits.max_execution_time == 300

    def test_custom_values(self):
        """Test custom resource limit values."""
        limits = ResourceLimits(
            max_memory_mb=1024,
            max_cpu_percent=50.0,
            max_file_descriptors=512,
            max_execution_time=120,
        )
        assert limits.max_memory_mb == 1024
        assert limits.max_cpu_percent == 50.0
        assert limits.max_file_descriptors == 512
        assert limits.max_execution_time == 120


class TestProcessInfo:
    """Test ProcessInfo dataclass."""

    def test_creation(self):
        """Test ProcessInfo creation."""
        info = ProcessInfo(
            id="test-id",
            provider_name="claude_cli",
            binary="claude",
            args=["-p", "--output-format", "text"],
        )

        assert info.id == "test-id"
        assert info.provider_name == "claude_cli"
        assert info.binary == "claude"
        assert info.args == ["-p", "--output-format", "text"]
        assert info.process is None
        assert not info.session_mode
        assert info.cwd is None
        assert isinstance(info.created_at, float)
        assert isinstance(info.last_accessed, float)

    def test_is_alive_no_process(self):
        """Test is_alive when no process is set."""
        info = ProcessInfo(
            id="test-id", provider_name="claude_cli", binary="claude", args=[]
        )
        assert not info.is_alive

    def test_is_alive_with_process(self):
        """Test is_alive with a mock process."""
        mock_process = Mock()
        mock_process.poll.return_value = None  # Process is running

        info = ProcessInfo(
            id="test-id", provider_name="claude_cli", binary="claude", args=[]
        )
        info.process = mock_process

        assert info.is_alive

        # Test dead process
        mock_process.poll.return_value = 0  # Process exited
        assert not info.is_alive

    def test_idle_time(self):
        """Test idle time calculation."""
        info = ProcessInfo(
            id="test-id", provider_name="claude_cli", binary="claude", args=[]
        )

        # Sleep briefly and check idle time
        time.sleep(0.1)
        idle_time = info.idle_time
        assert idle_time >= 0.1
        assert idle_time < 0.2  # Should be small

    def test_update_access_time(self):
        """Test access time update."""
        info = ProcessInfo(
            id="test-id", provider_name="claude_cli", binary="claude", args=[]
        )

        original_time = info.last_accessed
        time.sleep(0.1)
        info.update_access_time()

        assert info.last_accessed > original_time


class TestCLIProcessManager:
    """Test CLIProcessManager class."""

    @pytest.fixture
    def manager(self):
        """Create a CLIProcessManager instance for testing."""
        return CLIProcessManager(
            max_processes=5,
            idle_timeout=10,
            enable_monitoring=False,  # Disable monitoring for tests
        )

    @pytest.fixture
    def provider_cfg(self):
        """Create a test provider configuration."""
        return ProviderCfg(
            mode="cli",
            provider_type="cli",
            binary="echo",  # Use echo as a safe test command
            args=["test"],
            model="test-model",
        )

    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.max_processes == 5
        assert manager.idle_timeout == 10
        assert not manager.enable_monitoring
        assert len(manager.processes) == 0
        assert len(manager.provider_processes) == 0
        assert manager._monitoring_task is None

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, manager):
        """Test monitoring start and stop."""
        # Enable monitoring for this test
        manager.enable_monitoring = True

        await manager.start_monitoring()
        assert manager._monitoring_task is not None
        assert not manager._monitoring_task.done()

        await manager.stop_monitoring()
        assert manager._monitoring_task is None

    @pytest.mark.asyncio
    async def test_spawn_process_oneshot(self, manager, provider_cfg):
        """Test spawning a one-shot process."""
        process_id = await manager.spawn_process(
            provider_name="test_cli", cfg=provider_cfg, session_mode=False
        )

        assert process_id is not None
        assert process_id in manager.processes

        process_info = manager.processes[process_id]
        assert process_info.id == process_id
        assert process_info.provider_name == "test_cli"
        assert process_info.binary == "echo"
        assert process_info.args == ["test"]
        assert not process_info.session_mode

        # Clean up
        await manager.terminate_process(process_id)

    @pytest.mark.asyncio
    async def test_spawn_process_interactive(self, manager):
        """Test spawning an interactive process."""
        cfg = ProviderCfg(
            mode="interactive",
            provider_type="cli",
            binary="cat",  # Use cat for interactive testing
            args=[],
        )

        process_id = await manager.spawn_process(
            provider_name="test_interactive", cfg=cfg, session_mode=True
        )

        assert process_id is not None
        assert process_id in manager.processes

        process_info = manager.processes[process_id]
        assert process_info.session_mode
        assert process_info.output_queue is not None
        assert process_info.error_queue is not None
        assert process_info.process is not None
        assert process_info.is_alive

        # Clean up
        await manager.terminate_process(process_id)

    @pytest.mark.asyncio
    async def test_process_limit(self, manager, provider_cfg):
        """Test process limit enforcement."""
        process_ids = []

        # Spawn up to the limit
        for i in range(manager.max_processes):
            process_id = await manager.spawn_process(
                provider_name=f"test_cli_{i}", cfg=provider_cfg, session_mode=False
            )
            process_ids.append(process_id)

        # Try to spawn one more - should fail
        with pytest.raises(ProcessLimitError):
            await manager.spawn_process(
                provider_name="test_cli_overflow", cfg=provider_cfg, session_mode=False
            )

        # Clean up
        for process_id in process_ids:
            await manager.terminate_process(process_id)

    @pytest.mark.asyncio
    async def test_send_command_oneshot(self, manager, provider_cfg):
        """Test sending command to one-shot process."""
        process_id = await manager.spawn_process(
            provider_name="test_cli", cfg=provider_cfg, session_mode=False
        )

        stdout, stderr = await manager.send_command(process_id, "Hello World")

        # echo should return the test args + command
        assert "Hello World" in stdout
        assert stderr == ""

        # Clean up
        await manager.terminate_process(process_id)

    @pytest.mark.asyncio
    async def test_send_command_nonexistent(self, manager):
        """Test sending command to non-existent process."""
        with pytest.raises(ProcessPoolError, match="Process .* not found"):
            await manager.send_command("nonexistent", "test")

    @pytest.mark.asyncio
    async def test_get_process(self, manager, provider_cfg):
        """Test getting process information."""
        process_id = await manager.spawn_process(
            provider_name="test_cli", cfg=provider_cfg, session_mode=False
        )

        # Test existing process
        process_info = manager.get_process(process_id)
        assert process_info is not None
        assert process_info.id == process_id

        # Test non-existent process
        assert manager.get_process("nonexistent") is None

        # Clean up
        await manager.terminate_process(process_id)

    @pytest.mark.asyncio
    async def test_list_processes(self, manager, provider_cfg):
        """Test listing processes."""
        # Initially empty
        processes = manager.list_processes()
        assert len(processes) == 0

        # Spawn some processes
        process_id1 = await manager.spawn_process(
            provider_name="test_cli_1", cfg=provider_cfg, session_mode=False
        )
        process_id2 = await manager.spawn_process(
            provider_name="test_cli_2", cfg=provider_cfg, session_mode=False
        )

        # List all processes
        processes = manager.list_processes()
        assert len(processes) == 2

        # Filter by provider
        processes = manager.list_processes(provider_name="test_cli_1")
        assert len(processes) == 1
        assert processes[0].id == process_id1

        # Clean up
        await manager.terminate_process(process_id1)
        await manager.terminate_process(process_id2)

    @pytest.mark.asyncio
    async def test_terminate_process(self, manager):
        """Test process termination."""
        cfg = ProviderCfg(
            mode="interactive", provider_type="cli", binary="cat", args=[]
        )

        process_id = await manager.spawn_process(
            provider_name="test_interactive", cfg=cfg, session_mode=True
        )

        # Verify process is alive
        process_info = manager.get_process(process_id)
        assert process_info.is_alive

        # Terminate process
        result = await manager.terminate_process(process_id)
        assert result is True

        # Verify process is cleaned up
        assert process_id not in manager.processes

        # Try to terminate again - should return False
        result = await manager.terminate_process(process_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_single_process(self, manager, provider_cfg):
        """Test health check for a single process."""
        process_id = await manager.spawn_process(
            provider_name="test_cli", cfg=provider_cfg, session_mode=False
        )

        health = await manager.health_check(process_id)

        assert health["total_processes"] == 1
        assert len(health["processes"]) == 1

        process_health = health["processes"][0]
        assert process_health["id"] == process_id
        assert process_health["provider"] == "test_cli"
        assert not process_health["session_mode"]

        # Clean up
        await manager.terminate_process(process_id)

    @pytest.mark.asyncio
    async def test_health_check_all_processes(self, manager, provider_cfg):
        """Test health check for all processes."""
        # Spawn multiple processes
        process_ids = []
        for i in range(3):
            process_id = await manager.spawn_process(
                provider_name=f"test_cli_{i}", cfg=provider_cfg, session_mode=False
            )
            process_ids.append(process_id)

        health = await manager.health_check()

        assert health["total_processes"] == 3
        assert len(health["processes"]) == 3

        # Clean up
        for process_id in process_ids:
            await manager.terminate_process(process_id)

    @pytest.mark.asyncio
    async def test_health_check_nonexistent_process(self, manager):
        """Test health check for non-existent process."""
        health = await manager.health_check("nonexistent")
        assert "error" in health
        assert "not found" in health["error"]

    @pytest.mark.asyncio
    async def test_shutdown(self, manager, provider_cfg):
        """Test manager shutdown."""
        # Spawn some processes
        process_ids = []
        for i in range(3):
            process_id = await manager.spawn_process(
                provider_name=f"test_cli_{i}", cfg=provider_cfg, session_mode=False
            )
            process_ids.append(process_id)

        assert len(manager.processes) == 3

        # Shutdown
        await manager.shutdown(timeout=5)

        # All processes should be cleaned up
        assert len(manager.processes) == 0

    @pytest.mark.asyncio
    async def test_cleanup_idle_processes(self, manager, provider_cfg):
        """Test cleanup of idle processes."""
        # Set very short idle timeout for testing
        manager.idle_timeout = 0.1

        process_id = await manager.spawn_process(
            provider_name="test_cli", cfg=provider_cfg, session_mode=False
        )

        # Wait for process to become idle
        await asyncio.sleep(0.2)

        # Trigger cleanup
        await manager._cleanup_idle_processes()

        # Process should be cleaned up
        assert process_id not in manager.processes

    @pytest.mark.asyncio
    async def test_resource_monitoring(self, manager):
        """Test resource usage monitoring."""
        cfg = ProviderCfg(
            mode="interactive", provider_type="cli", binary="cat", args=[]
        )

        process_id = await manager.spawn_process(
            provider_name="test_interactive", cfg=cfg, session_mode=True
        )

        # Run resource check
        await manager._check_resource_usage()

        # Process should still exist (no limits exceeded)
        assert process_id in manager.processes

        # Clean up
        await manager.terminate_process(process_id)


class TestSingletonFunctions:
    """Test singleton manager functions."""

    def test_get_cli_manager(self):
        """Test getting singleton instance."""
        manager1 = get_cli_manager()
        manager2 = get_cli_manager()

        assert manager1 is manager2
        assert isinstance(manager1, CLIProcessManager)

    @pytest.mark.asyncio
    async def test_initialize_cli_manager(self):
        """Test initializing singleton with custom options."""
        manager = await initialize_cli_manager(
            max_processes=10, idle_timeout=60, enable_monitoring=False
        )

        assert manager.max_processes == 10
        assert manager.idle_timeout == 60
        assert not manager.enable_monitoring

        # Clean up
        await shutdown_cli_manager()

    @pytest.mark.asyncio
    async def test_shutdown_cli_manager(self):
        """Test shutting down singleton."""
        # Initialize manager
        manager = await initialize_cli_manager(enable_monitoring=False)

        # Shutdown
        await shutdown_cli_manager()

        # Should not raise an error if called again
        await shutdown_cli_manager()


class TestErrorHandling:
    """Test error handling scenarios."""

    @pytest.fixture
    def manager(self):
        """Create a manager for error testing."""
        return CLIProcessManager(max_processes=1, enable_monitoring=False)

    @pytest.mark.asyncio
    async def test_spawn_process_invalid_binary(self, manager):
        """Test spawning process with invalid binary."""
        cfg = ProviderCfg(
            mode="cli", provider_type="cli", binary="/nonexistent/binary", args=[]
        )

        with pytest.raises(ProcessPoolError):
            await manager.spawn_process(
                provider_name="test_invalid", cfg=cfg, session_mode=False
            )

    @pytest.mark.asyncio
    async def test_send_command_timeout(self, manager):
        """Test command timeout."""
        cfg = ProviderCfg(
            mode="cli",
            provider_type="cli",
            binary="sleep",
            args=["10"],  # Sleep for 10 seconds
        )

        process_id = await manager.spawn_process(
            provider_name="test_slow", cfg=cfg, session_mode=False
        )

        with pytest.raises(ProcessTimeoutError):
            await manager.send_command(process_id, "test", timeout=1)

        # Clean up
        await manager.terminate_process(process_id, force=True)


class TestIntegrationScenarios:
    """Integration tests with realistic scenarios."""

    @pytest.mark.asyncio
    async def test_claude_cli_simulation(self):
        """Test simulation of claude CLI usage."""
        manager = CLIProcessManager(enable_monitoring=False)

        # Simulate claude CLI configuration
        cfg = ProviderCfg(
            mode="cli",
            provider_type="cli",
            binary="echo",  # Simulate claude
            args=["-p", "--output-format", "text"],
            model="sonnet",
        )

        try:
            # Spawn process
            process_id = await manager.spawn_process(
                provider_name="claude_cli", cfg=cfg, cwd="/tmp"
            )

            # Send a command
            stdout, stderr = await manager.send_command(
                process_id, "Write a hello world function in Python"
            )

            assert "Write a hello world function in Python" in stdout

            # Check health
            health = await manager.health_check(process_id)
            assert health["total_processes"] == 1

        finally:
            await manager.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_provider_management(self):
        """Test managing multiple different providers."""
        manager = CLIProcessManager(enable_monitoring=False)

        providers = [
            ("claude_cli", ProviderCfg(mode="cli", binary="echo", args=["-claude"])),
            ("codex_cli", ProviderCfg(mode="cli", binary="echo", args=["-codex"])),
            ("gemini_cli", ProviderCfg(mode="cli", binary="echo", args=["-gemini"])),
        ]

        process_ids = []

        try:
            # Spawn processes for each provider
            for provider_name, cfg in providers:
                process_id = await manager.spawn_process(
                    provider_name=provider_name, cfg=cfg
                )
                process_ids.append(process_id)

            # Test each provider
            for i, (process_id, (provider_name, cfg)) in enumerate(
                zip(process_ids, providers, strict=False)
            ):
                stdout, stderr = await manager.send_command(
                    process_id, f"Test command {i}"
                )
                assert cfg.args[0] in stdout  # Should contain provider-specific arg
                assert f"Test command {i}" in stdout

            # Check all processes are tracked
            all_processes = manager.list_processes()
            assert len(all_processes) == 3

            # Check provider-specific listing
            claude_processes = manager.list_processes(provider_name="claude_cli")
            assert len(claude_processes) == 1
            assert claude_processes[0].provider_name == "claude_cli"

        finally:
            await manager.shutdown()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__])
