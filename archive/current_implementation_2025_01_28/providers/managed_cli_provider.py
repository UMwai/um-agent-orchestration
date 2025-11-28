"""
Managed CLI Provider - Integration layer between CLI Process Manager and existing providers.

This module provides a bridge between the new CLI Process Manager and the existing
provider system, allowing for gradual migration and enhanced process management.
"""

from __future__ import annotations

import asyncio
from typing import Any

from orchestrator.cli_manager import ProcessPoolError, ProcessTimeoutError, get_cli_manager
from orchestrator.settings import ProviderCfg


class ManagedCLIProvider:
    """
    Managed CLI provider that uses the CLI Process Manager for enhanced
    process lifecycle management while maintaining compatibility with
    the existing provider interface.
    """

    def __init__(self):
        self.cli_manager = get_cli_manager()
        self._active_sessions: dict[str, str] = {}  # provider_name -> process_id

    async def call_cli_managed(
        self,
        provider_name: str,
        prompt: str,
        cfg: ProviderCfg,
        cwd: str | None = None,
        timeout: int | None = None,
        session_mode: bool = False,
    ) -> str:
        """
        Call a CLI provider using the managed process pool.

        Args:
            provider_name: Name of the provider
            prompt: The prompt to send
            cfg: Provider configuration
            cwd: Working directory
            timeout: Command timeout
            session_mode: Whether to use session mode for reuse

        Returns:
            Response from the CLI tool

        Raises:
            RuntimeError: If the CLI call fails
        """
        process_id = None

        try:
            # Check for existing session
            if session_mode and provider_name in self._active_sessions:
                existing_id = self._active_sessions[provider_name]
                if self.cli_manager.get_process(existing_id):
                    process_id = existing_id

            # Create new process if needed
            if not process_id:
                process_id = await self.cli_manager.spawn_process(
                    provider_name=provider_name, cfg=cfg, cwd=cwd, session_mode=session_mode
                )

                if session_mode:
                    self._active_sessions[provider_name] = process_id

            # Send command
            stdout, stderr = await self.cli_manager.send_command(
                process_id=process_id, command=prompt, timeout=timeout
            )

            # Handle stderr
            if stderr and not stdout:
                raise RuntimeError(f"CLI command failed: {stderr}")

            return stdout

        except (ProcessPoolError, ProcessTimeoutError) as e:
            # Clean up failed session
            if session_mode and provider_name in self._active_sessions:
                del self._active_sessions[provider_name]
            raise RuntimeError(f"Managed CLI call failed: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error in managed CLI call: {e}") from e

    async def cleanup_session(self, provider_name: str) -> bool:
        """
        Clean up a specific provider session.

        Args:
            provider_name: Name of the provider to clean up

        Returns:
            True if session was cleaned up, False if no session existed
        """
        if provider_name not in self._active_sessions:
            return False

        process_id = self._active_sessions[provider_name]
        success = await self.cli_manager.terminate_process(process_id)

        if success:
            del self._active_sessions[provider_name]

        return success

    async def cleanup_all_sessions(self) -> int:
        """
        Clean up all active sessions.

        Returns:
            Number of sessions cleaned up
        """
        count = 0
        providers_to_cleanup = list(self._active_sessions.keys())

        for provider_name in providers_to_cleanup:
            if await self.cleanup_session(provider_name):
                count += 1

        return count

    def get_session_info(self) -> dict[str, dict[str, Any]]:
        """
        Get information about active sessions.

        Returns:
            Dictionary mapping provider names to session info
        """
        session_info = {}

        for provider_name, process_id in self._active_sessions.items():
            process_info = self.cli_manager.get_process(process_id)
            if process_info:
                session_info[provider_name] = {
                    "process_id": process_id,
                    "alive": process_info.is_alive,
                    "idle_time": process_info.idle_time,
                    "created_at": process_info.created_at,
                    "resource_usage": process_info.resource_usage,
                }

        return session_info


# Global instance for easy access
_managed_provider: ManagedCLIProvider | None = None


def get_managed_provider() -> ManagedCLIProvider:
    """Get the global managed CLI provider instance."""
    global _managed_provider
    if _managed_provider is None:
        _managed_provider = ManagedCLIProvider()
    return _managed_provider


# Enhanced provider functions that use the managed CLI provider
async def call_claude_cli_managed(
    prompt: str, cfg: ProviderCfg, cwd: str | None = None, session_mode: bool = False
) -> str:
    """Enhanced Claude CLI call with managed process pool."""
    provider = get_managed_provider()
    return await provider.call_cli_managed(
        provider_name="claude_cli", prompt=prompt, cfg=cfg, cwd=cwd, session_mode=session_mode
    )


async def call_codex_cli_managed(
    prompt: str, cfg: ProviderCfg, cwd: str | None = None, session_mode: bool = False
) -> str:
    """Enhanced Codex CLI call with managed process pool."""
    provider = get_managed_provider()
    return await provider.call_cli_managed(
        provider_name="codex_cli", prompt=prompt, cfg=cfg, cwd=cwd, session_mode=session_mode
    )


async def call_gemini_cli_managed(
    prompt: str, cfg: ProviderCfg, cwd: str | None = None, session_mode: bool = False
) -> str:
    """Enhanced Gemini CLI call with managed process pool."""
    provider = get_managed_provider()
    return await provider.call_cli_managed(
        provider_name="gemini_cli", prompt=prompt, cfg=cfg, cwd=cwd, session_mode=session_mode
    )


async def call_cursor_cli_managed(
    prompt: str, cfg: ProviderCfg, cwd: str | None = None, session_mode: bool = False
) -> str:
    """Enhanced Cursor CLI call with managed process pool."""
    provider = get_managed_provider()
    return await provider.call_cli_managed(
        provider_name="cursor_cli", prompt=prompt, cfg=cfg, cwd=cwd, session_mode=session_mode
    )


# Compatibility wrapper for gradual migration
def call_cli_with_fallback(
    provider_name: str,
    prompt: str,
    cfg: ProviderCfg,
    cwd: str | None = None,
    use_managed: bool = True,
) -> str:
    """
    Call CLI provider with fallback to original implementation.

    This function provides a compatibility layer during migration to the
    managed CLI system. If the managed call fails, it falls back to the
    original synchronous implementation.

    Args:
        provider_name: Name of the provider
        prompt: The prompt to send
        cfg: Provider configuration
        cwd: Working directory
        use_managed: Whether to try managed approach first

    Returns:
        Response from the CLI tool
    """
    if not use_managed:
        # Use original implementation directly
        return _call_original_cli(provider_name, prompt, cfg, cwd)

    try:
        # Try managed approach
        return asyncio.run(
            get_managed_provider().call_cli_managed(
                provider_name=provider_name,
                prompt=prompt,
                cfg=cfg,
                cwd=cwd,
                session_mode=False,  # One-shot for compatibility
            )
        )
    except Exception:
        # Fall back to original implementation
        return _call_original_cli(provider_name, prompt, cfg, cwd)


def _call_original_cli(
    provider_name: str, prompt: str, cfg: ProviderCfg, cwd: str | None = None
) -> str:
    """Call original CLI implementation as fallback."""
    import subprocess

    binary = cfg.binary or provider_name.replace("_cli", "")
    args = cfg.args or []
    full_cmd = [binary] + args + [prompt]

    proc = subprocess.run(full_cmd, cwd=cwd, capture_output=True, text=True)

    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"{provider_name} CLI failed")

    return proc.stdout
