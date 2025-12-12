"""
Autonomous Harness for long-running agent tasks

Enhanced with parallel tool execution capabilities for improved throughput.
"""
import json
import time
import logging
import threading
import signal
import sys
from typing import List, Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum

from .agent_api import AgentAPI
from .tools import get_tool_definitions, get_tool_map, Tool
from pathlib import Path

logger = logging.getLogger(__name__)

# Load settings
SETTINGS_PATH = Path(__file__).parent.parent.parent / "config" / "settings.json"
try:
    with open(SETTINGS_PATH, "r") as f:
        SETTINGS = json.load(f)
except Exception:
    SETTINGS = {
        "auto_mode": False,
        "max_loops": None,
        "allow_list": ["read_file"],
        "supervisor_interval_seconds": 5,
        "context_pruning_threshold_chars": 100000
    }

# Constants for context management
MAX_RESULT_SIZE = 100 * 1024  # 100KB max for single tool result
MAX_MESSAGE_SIZE = 50 * 1024  # 50KB max per message
TOOL_RESULT_SUMMARY_LENGTH = 500  # Chars to keep from large tool results


class ExecutionMode(Enum):
    """Tool execution mode"""
    SERIAL = "serial"
    PARALLEL = "parallel"
    AUTO = "auto"  # Automatically decide based on tool independence


@dataclass
class ToolExecutionResult:
    """Result from executing a tool"""
    tool_id: str
    tool_name: str
    success: bool
    result: str
    execution_time: float


class AutonomousHarness:
    """
    Autonomous agent harness for executing long-running tasks.

    Enhanced with parallel tool execution for improved throughput when
    multiple independent tools are called in a single step.

    Now supports 24/7 operation with Supervisor loop.
    """

    # Tools that must be executed serially (have side effects on shared state)
    SERIAL_ONLY_TOOLS: Set[str] = {"edit_file"}  # File edits should be sequential

    # Tools that are safe to parallelize
    PARALLELIZABLE_TOOLS: Set[str] = {"read_file", "bash"}

    # Tools allowed to auto-run in 24/7 mode
    ALLOW_LIST: Set[str] = set(SETTINGS.get("allow_list", []))

    def __init__(
        self,
        agent_api: AgentAPI,
        execution_mode: ExecutionMode = ExecutionMode.AUTO,
        max_parallel_tools: int = 5,
    ):
        self.agent_api = agent_api
        self.messages: List[Dict[str, Any]] = []
        self._message_lock = threading.Lock()  # Thread safety for message access
        self.tool_map = get_tool_map()
        self.tools_def = get_tool_definitions()
        self.execution_mode = execution_mode
        self.max_parallel_tools = max_parallel_tools

        # Statistics
        self.total_tool_calls = 0
        self.parallel_batches = 0
        self.serial_executions = 0
        self.total_tool_time = 0.0

    def run_task(
        self,
        task_description: str,
        max_steps: int = 50,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """
        Run an autonomous task with the agent.

        Args:
            task_description: Description of the task to perform
            max_steps: Maximum number of agent steps
            parallel: Whether to allow parallel tool execution

        Returns:
            Dict with task results and statistics
        """
        print(f"🚀 Starting Autonomous Task: {task_description}")
        if parallel and self.execution_mode != ExecutionMode.SERIAL:
            print(f"   ⚡ Parallel tool execution enabled (max {self.max_parallel_tools})")

        # Reset messages for new task
        with self._message_lock:
            self.messages = []
            # Initial user message
            self.messages.append({
                "role": "user",
                "content": f"You are an autonomous coding agent. Your task is: {task_description}\n\nYou have access to tools to execute bash commands, read files, and write files. Use them to investigate and solve the problem."
            })

        step_count = 0
        task_started = time.time()

        while True:
            # Check for infinite loop break
            if max_steps and step_count >= max_steps:
                print(f"⚠️ Reached maximum step count ({max_steps}).")
                break

            step_count += 1
            print(f"\n🔄 Step {step_count}")

            # Prune context if needed
            self._prune_context()

            # Call API
            try:
                with self._message_lock:
                    messages_copy = self.messages.copy()

                response_message = self.agent_api.chat_completion(
                    messages=messages_copy,
                    tools=self.tools_def
                )
            except Exception as e:
                print(f"❌ API Error: {e}")
                logger.error(f"API Error in step {step_count}: {e}", exc_info=True)
                break

            # Add assistant response to history
            with self._message_lock:
                self.messages.append(response_message)

            # Check content
            content_blocks = response_message.get("content", [])

            # If string content (legacy/mock), wrap it
            if isinstance(content_blocks, str):
                print(f"🤖 {content_blocks}")
                break

            tool_calls = [b for b in content_blocks if b.get("type") == "tool_use"]
            text_blocks = [b for b in content_blocks if b.get("type") == "text"]

            for txt in text_blocks:
                print(f"🤖 {txt.get('text')}")

            if not tool_calls:
                print("✅ No more tools to run. Task considered complete.")
                break

            # Execute tools (parallel or serial based on settings)
            if parallel and self._can_parallelize_tools(tool_calls):
                tool_results = self._execute_tools_parallel(tool_calls)
            else:
                tool_results = self._execute_tools_serial(tool_calls)

            # Append tool results to history
            with self._message_lock:
                self.messages.append({
                    "role": "user",
                    "content": tool_results
                })

        task_duration = time.time() - task_started

        # Return execution summary
        return {
            "steps": step_count,
            "duration": task_duration,
            "tool_calls": self.total_tool_calls,
            "parallel_batches": self.parallel_batches,
            "serial_executions": self.serial_executions,
            "total_tool_time": self.total_tool_time,
            "completed": step_count < max_steps if max_steps else True,
        }

    def _can_parallelize_tools(self, tool_calls: List[Dict]) -> bool:
        """
        Determine if tool calls can be executed in parallel.

        Rules:
        1. If execution_mode is SERIAL, always return False
        2. If any tool is in SERIAL_ONLY_TOOLS, return False if there are conflicts
        3. If execution_mode is PARALLEL, always return True (user knows best)
        4. If execution_mode is AUTO, analyze tool independence
        """
        if self.execution_mode == ExecutionMode.SERIAL:
            return False

        if len(tool_calls) <= 1:
            return False  # No benefit to parallelizing a single call

        if self.execution_mode == ExecutionMode.PARALLEL:
            return True

        # AUTO mode: analyze tool calls
        tool_names = [tc.get("name") for tc in tool_calls]

        # Check if any tool is serial-only
        if any(name in self.SERIAL_ONLY_TOOLS for name in tool_names):
            # Check for file conflicts in edit operations
            edit_paths = set()
            for tc in tool_calls:
                if tc.get("name") == "edit_file":
                    path = tc.get("input", {}).get("path", "")
                    if path in edit_paths:
                        return False  # Same file edited twice, must be serial
                    edit_paths.add(path)

            # If editing different files, can still parallelize
            if len(edit_paths) > 1:
                return True
            # If there's only one edit, parallelize with reads
            return len(tool_calls) > len(edit_paths)

        # All tools are parallelizable
        return all(
            name in self.PARALLELIZABLE_TOOLS or name not in self.SERIAL_ONLY_TOOLS
            for name in tool_names
        )

    def _execute_tools_serial(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute tools one by one (original behavior)"""
        tool_results = []
        self.serial_executions += 1

        for tc in tool_calls:
            result = self._execute_single_tool(tc)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": result.tool_id,
                "content": result.result
            })

        return tool_results

    def _execute_tools_parallel(self, tool_calls: List[Dict]) -> List[Dict]:
        """Execute multiple tools concurrently"""
        self.parallel_batches += 1
        tool_results: List[Dict] = []
        result_map: Dict[str, ToolExecutionResult] = {}

        print(f"   ⚡ Executing {len(tool_calls)} tools in parallel")

        with ThreadPoolExecutor(max_workers=min(len(tool_calls), self.max_parallel_tools)) as executor:
            futures = {
                executor.submit(self._execute_single_tool, tc): tc.get("id")
                for tc in tool_calls
            }

            for future in as_completed(futures):
                tool_id = futures[future]
                try:
                    result = future.result()
                    result_map[tool_id] = result
                except Exception as e:
                    logger.error(f"Tool execution error for {tool_id}: {e}", exc_info=True)
                    result_map[tool_id] = ToolExecutionResult(
                        tool_id=tool_id,
                        tool_name="unknown",
                        success=False,
                        result=f"Error: {e}",
                        execution_time=0.0,
                    )

        # Maintain original order of tool calls
        for tc in tool_calls:
            tool_id = tc.get("id")
            if tool_id in result_map:
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_map[tool_id].result
                })

        return tool_results

    def _execute_single_tool(self, tc: Dict) -> ToolExecutionResult:
        """Execute a single tool and return structured result"""
        tool_name = tc.get("name")
        tool_id = tc.get("id")
        tool_input = tc.get("input", {})

        self.total_tool_calls += 1
        start_time = time.time()

        print(f"🛠️ Executing {tool_name}...")

        if tool_name in self.tool_map:
            tool = self.tool_map[tool_name]
            try:
                result_text = tool.execute(**tool_input)
                success = True
            except Exception as e:
                result_text = f"Error executing tool: {e}"
                success = False
                logger.error(f"Tool {tool_name} failed: {e}", exc_info=True)
        else:
            result_text = f"Error: Tool {tool_name} not found"
            success = False

        # Truncate large results to prevent memory issues
        if len(result_text) > MAX_RESULT_SIZE:
            truncated_msg = f"\n\n[... Result truncated from {len(result_text)} to {MAX_RESULT_SIZE} chars ...]"
            result_text = result_text[:MAX_RESULT_SIZE] + truncated_msg
            logger.warning(f"Tool {tool_name} result truncated from {len(result_text)} chars")

        execution_time = time.time() - start_time
        self.total_tool_time += execution_time

        print(f"   -> Result len: {len(result_text)} chars ({execution_time:.2f}s)")

        return ToolExecutionResult(
            tool_id=tool_id,
            tool_name=tool_name,
            success=success,
            result=result_text,
            execution_time=execution_time,
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        return {
            "total_tool_calls": self.total_tool_calls,
            "parallel_batches": self.parallel_batches,
            "serial_executions": self.serial_executions,
            "total_tool_time": self.total_tool_time,
            "avg_tool_time": self.total_tool_time / max(1, self.total_tool_calls),
            "execution_mode": self.execution_mode.value,
            "max_parallel_tools": self.max_parallel_tools,
        }

    def _prune_context(self):
        """
        Manage memory by summarizing or pruning old messages.

        Strategy:
        1. Truncate individual oversized messages
        2. Keep first message (system/task)
        3. Keep tool result summaries rather than full results
        4. Keep recent messages in full
        """
        threshold = SETTINGS.get("context_pruning_threshold_chars", 100000)

        with self._message_lock:
            # First pass: truncate individual oversized messages
            for msg in self.messages:
                msg_str = str(msg)
                if len(msg_str) > MAX_MESSAGE_SIZE:
                    # For user messages with tool results, summarize them
                    if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                        for block in msg["content"]:
                            if block.get("type") == "tool_result":
                                content = block.get("content", "")
                                if len(content) > TOOL_RESULT_SUMMARY_LENGTH:
                                    summary = content[:TOOL_RESULT_SUMMARY_LENGTH] + f"\n[... truncated {len(content) - TOOL_RESULT_SUMMARY_LENGTH} chars ...]"
                                    block["content"] = summary

            current_chars = sum(len(str(m)) for m in self.messages)

            if current_chars > threshold:
                print(f"🧹 Pruning context ({current_chars} > {threshold} chars)...")

                if len(self.messages) > 10:
                    # Keep first message (task description) and last 10 messages
                    # This preserves recent context while removing old middle messages
                    kept_messages = [self.messages[0]] + self.messages[-10:]
                    removed_count = len(self.messages) - len(kept_messages)
                    self.messages = kept_messages

                    new_chars = sum(len(str(m)) for m in self.messages)
                    print(f"   -> Pruned {removed_count} messages ({current_chars} -> {new_chars} chars)")


class Supervisor:
    """
    Watcher that ensures the agent runs 24/7.
    Restarts the harness if it crashes or stops unexpectedly.

    Features:
    - Max restart limit to prevent infinite crash loops
    - Exponential backoff on repeated failures
    - Graceful shutdown on SIGINT/SIGTERM
    """

    MAX_RESTARTS = 10  # Maximum restarts before giving up
    INITIAL_BACKOFF = 5  # Initial backoff in seconds
    MAX_BACKOFF = 300  # Maximum backoff (5 minutes)

    def __init__(self, harness: AutonomousHarness):
        self.harness = harness
        self._shutdown_requested = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\n🛑 Received signal {signum}, shutting down gracefully...")
        self._shutdown_requested = True

    def run_forever(self, task_description: str):
        """
        Run the agent in a supervised loop with restart capability.

        Args:
            task_description: Task for the agent to work on
        """
        print(f"♾️ Starting 24/7 Supervisor for: {task_description}")
        restart_count = 0
        consecutive_failures = 0
        backoff_time = self.INITIAL_BACKOFF

        while not self._shutdown_requested:
            if restart_count >= self.MAX_RESTARTS:
                print(f"❌ Reached maximum restart limit ({self.MAX_RESTARTS}). Exiting.")
                break

            try:
                print(f"\n🚀 Starting Agent Loop (Iteration {restart_count + 1})")

                # Run with large step limit to allow long-running tasks
                result = self.harness.run_task(task_description, max_steps=1000)

                # If it finishes naturally, it might be complete
                if result.get("completed"):
                    print("✅ Agent finished task successfully.")
                    consecutive_failures = 0  # Reset failure count on success
                    backoff_time = self.INITIAL_BACKOFF

                    print("   Waiting 10s before restart...")
                    time.sleep(10)
                else:
                    print("⚠️ Agent stopped without completion.")

            except KeyboardInterrupt:
                print("\n🛑 Stopped by user (KeyboardInterrupt)")
                break

            except Exception as e:
                consecutive_failures += 1
                restart_count += 1

                print(f"\n💥 Agent Crashed: {e}")
                logger.error(f"Agent crash (restart {restart_count}): {e}", exc_info=True)

                # Calculate exponential backoff
                current_backoff = min(backoff_time * (2 ** (consecutive_failures - 1)), self.MAX_BACKOFF)

                print(f"   Restarting in {current_backoff}s... (failure {consecutive_failures})")
                time.sleep(current_backoff)

        print("\n👋 Supervisor shutdown complete")


class ParallelAutonomousHarness(AutonomousHarness):
    """
    Extended harness that can run multiple independent subtasks in parallel.

    Uses the parallel executor for batch task execution.

    IMPORTANT: The agent_api instance passed to this class MUST be thread-safe,
    or each subtask will create its own AgentAPI instance for isolation.
    """

    def __init__(
        self,
        agent_api: AgentAPI,
        max_parallel_agents: int = 3,
        **kwargs,
    ):
        super().__init__(agent_api, **kwargs)
        self.max_parallel_agents = max_parallel_agents

    def run_parallel_subtasks(
        self,
        subtasks: List[str],
        max_steps_per_task: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Run multiple independent subtasks in parallel.

        Each subtask gets its own agent context and runs independently.

        Args:
            subtasks: List of task descriptions
            max_steps_per_task: Maximum steps for each subtask

        Returns:
            List of results for each subtask
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results = []

        print(f"🚀 Running {len(subtasks)} subtasks in parallel")

        with ThreadPoolExecutor(max_workers=self.max_parallel_agents) as executor:
            futures = {
                executor.submit(self._run_subtask, subtask, max_steps_per_task): i
                for i, subtask in enumerate(subtasks)
            }

            for future in as_completed(futures):
                task_idx = futures[future]
                try:
                    result = future.result()
                    results.append({
                        "index": task_idx,
                        "subtask": subtasks[task_idx],
                        "result": result,
                    })
                except Exception as e:
                    logger.error(f"Subtask {task_idx} failed: {e}", exc_info=True)
                    results.append({
                        "index": task_idx,
                        "subtask": subtasks[task_idx],
                        "error": str(e),
                    })

        # Sort by original index
        results.sort(key=lambda x: x.get("index", 0))
        return results

    def _run_subtask(self, subtask: str, max_steps: int) -> Dict[str, Any]:
        """
        Run a single subtask in its own context.

        NOTE: Creates a new AutonomousHarness instance for thread isolation.
        If agent_api is thread-safe, we could reuse it, but creating new
        instances is safer for avoiding race conditions.
        """
        # Create new harness instance for complete isolation
        harness = AutonomousHarness(
            self.agent_api,  # Reuses same API client (must be thread-safe!)
            execution_mode=self.execution_mode,
            max_parallel_tools=self.max_parallel_tools,
        )
        return harness.run_task(subtask, max_steps=max_steps)
