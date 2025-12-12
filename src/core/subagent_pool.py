"""
Subagent Pool - Manages a pool of reusable agent instances for parallel execution.

Provides efficient agent lifecycle management with pre-warming, health checks,
and automatic scaling based on demand.
"""

import time
import logging
import uuid
from queue import Queue, Empty
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any
from threading import Lock, Thread, Event
from enum import Enum
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """State of a subagent instance"""
    IDLE = "idle"
    BUSY = "busy"
    WARMING = "warming"
    COOLING_DOWN = "cooling_down"
    ERROR = "error"


@dataclass
class SubagentInstance:
    """Represents a single subagent in the pool"""
    agent_id: str
    agent_type: str
    state: AgentState = AgentState.IDLE
    created_at: float = field(default_factory=time.time)
    last_used_at: Optional[float] = None
    task_count: int = 0
    error_count: int = 0
    current_task_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_available(self) -> bool:
        return self.state == AgentState.IDLE
    
    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at
    
    @property
    def idle_time(self) -> Optional[float]:
        if self.last_used_at is None:
            return self.age_seconds
        return time.time() - self.last_used_at


@dataclass
class PoolStats:
    """Statistics for the agent pool"""
    total_agents: int = 0
    idle_agents: int = 0
    busy_agents: int = 0
    error_agents: int = 0
    total_tasks_completed: int = 0
    total_errors: int = 0
    avg_task_duration: float = 0.0
    pool_utilization: float = 0.0


class SubagentPool:
    """
    Manages a pool of reusable subagent instances.
    
    Features:
    - Pre-warmed agent pool for faster task execution
    - Automatic cleanup of idle agents
    - Health monitoring and error handling
    - Dynamic scaling based on demand
    - Thread-safe operations
    """
    
    def __init__(
        self,
        pool_size: int = 5,
        agent_types: Optional[List[str]] = None,
        max_idle_time: float = 300.0,  # 5 minutes
        max_agent_lifetime: float = 3600.0,  # 1 hour
        warmup_on_init: bool = True,
    ):
        self.pool_size = pool_size
        self.agent_types = agent_types or ["generic"]
        self.max_idle_time = max_idle_time
        self.max_agent_lifetime = max_agent_lifetime
        
        self._agents: Dict[str, SubagentInstance] = {}
        self._available_queue: Queue[str] = Queue()
        self._busy_set: Set[str] = set()
        self._lock = Lock()
        self._shutdown = Event()
        
        self._task_durations: List[float] = []
        self._total_tasks_completed = 0
        self._total_errors = 0
        
        # Start maintenance thread
        self._maintenance_thread = Thread(target=self._maintenance_loop, daemon=True)
        self._maintenance_thread.start()
        
        # Optionally pre-warm the pool
        if warmup_on_init:
            self._warmup_pool()
    
    def _warmup_pool(self):
        """Pre-create agents to fill the pool"""
        logger.info(f"Warming up pool with {self.pool_size} agents")
        for i in range(self.pool_size):
            agent_type = self.agent_types[i % len(self.agent_types)]
            self._create_agent(agent_type)
    
    def _create_agent(self, agent_type: str) -> SubagentInstance:
        """Create a new agent instance"""
        agent_id = f"{agent_type}_{uuid.uuid4().hex[:8]}"
        agent = SubagentInstance(
            agent_id=agent_id,
            agent_type=agent_type,
            state=AgentState.IDLE,
        )
        
        with self._lock:
            self._agents[agent_id] = agent
            self._available_queue.put(agent_id)
            
        logger.debug(f"Created agent {agent_id}")
        return agent
    
    def acquire(
        self,
        agent_type: Optional[str] = None,
        timeout: float = 30.0,
    ) -> Optional[SubagentInstance]:
        """
        Acquire an available agent from the pool.
        
        Args:
            agent_type: Preferred agent type (creates new if needed)
            timeout: Maximum time to wait for an available agent
            
        Returns:
            SubagentInstance or None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self._shutdown.is_set():
                return None
                
            try:
                # Try to get an available agent
                agent_id = self._available_queue.get(timeout=0.5)
                
                with self._lock:
                    if agent_id not in self._agents:
                        continue  # Agent was removed
                        
                    agent = self._agents[agent_id]
                    
                    # Check if agent is still valid
                    if agent.age_seconds > self.max_agent_lifetime:
                        self._remove_agent(agent_id)
                        continue
                    
                    # Check agent type preference
                    if agent_type and agent.agent_type != agent_type:
                        # Put back and continue if wrong type
                        self._available_queue.put(agent_id)
                        continue
                    
                    # Mark as busy
                    agent.state = AgentState.BUSY
                    self._busy_set.add(agent_id)
                    
                    logger.debug(f"Acquired agent {agent_id}")
                    return agent
                    
            except Empty:
                # No agent available, try to create one if under limit
                with self._lock:
                    if len(self._agents) < self.pool_size * 2:  # Allow 2x for burst
                        agent = self._create_agent(agent_type or self.agent_types[0])
                        agent.state = AgentState.BUSY
                        # Remove from available queue since we're using it immediately
                        try:
                            self._available_queue.get_nowait()
                        except Empty:
                            pass
                        self._busy_set.add(agent.agent_id)
                        return agent
                        
        logger.warning(f"Timeout waiting for available agent")
        return None
    
    def release(
        self,
        agent_id: str,
        success: bool = True,
        task_duration: Optional[float] = None,
    ):
        """
        Return an agent to the pool after task completion.
        
        Args:
            agent_id: ID of the agent to release
            success: Whether the task completed successfully
            task_duration: Optional duration of the completed task
        """
        with self._lock:
            if agent_id not in self._agents:
                logger.warning(f"Attempted to release unknown agent {agent_id}")
                return
                
            agent = self._agents[agent_id]
            
            # Update agent stats
            agent.last_used_at = time.time()
            agent.task_count += 1
            agent.current_task_id = None
            
            if success:
                self._total_tasks_completed += 1
                if task_duration:
                    self._task_durations.append(task_duration)
                    # Keep only last 100 durations for avg calculation
                    if len(self._task_durations) > 100:
                        self._task_durations.pop(0)
            else:
                agent.error_count += 1
                self._total_errors += 1
                
                # Remove agents with too many errors
                if agent.error_count > 5:
                    agent.state = AgentState.ERROR
                    self._remove_agent(agent_id)
                    return
            
            # Return to available pool
            agent.state = AgentState.IDLE
            self._busy_set.discard(agent_id)
            self._available_queue.put(agent_id)
            
        logger.debug(f"Released agent {agent_id}")
    
    @contextmanager
    def get_agent(
        self,
        agent_type: Optional[str] = None,
        timeout: float = 30.0,
    ):
        """
        Context manager for acquiring and releasing an agent.
        
        Usage:
            with pool.get_agent(agent_type="backend") as agent:
                # Use agent
                result = do_task(agent)
        """
        agent = self.acquire(agent_type, timeout)
        if agent is None:
            raise TimeoutError("Could not acquire agent from pool")
            
        start_time = time.time()
        success = True
        try:
            yield agent
        except Exception:
            success = False
            raise
        finally:
            duration = time.time() - start_time
            self.release(agent.agent_id, success, duration)
    
    def _remove_agent(self, agent_id: str):
        """Remove an agent from the pool"""
        agent = self._agents.pop(agent_id, None)
        self._busy_set.discard(agent_id)
        if agent:
            logger.info(f"Removed agent {agent_id} (completed {agent.task_count} tasks)")
    
    def _maintenance_loop(self):
        """Background thread for pool maintenance"""
        while not self._shutdown.is_set():
            try:
                self._cleanup_idle_agents()
                self._ensure_minimum_pool()
            except Exception as e:
                logger.error(f"Maintenance error: {e}")
            
            self._shutdown.wait(timeout=30.0)  # Run every 30 seconds
    
    def _cleanup_idle_agents(self):
        """Remove agents that have been idle too long"""
        with self._lock:
            agents_to_remove = []
            
            for agent_id, agent in self._agents.items():
                if agent_id in self._busy_set:
                    continue
                    
                # Check idle time
                if agent.idle_time and agent.idle_time > self.max_idle_time:
                    agents_to_remove.append(agent_id)
                    
                # Check lifetime
                elif agent.age_seconds > self.max_agent_lifetime:
                    agents_to_remove.append(agent_id)
            
            for agent_id in agents_to_remove:
                self._remove_agent(agent_id)
    
    def _ensure_minimum_pool(self):
        """Ensure we have at least pool_size agents available"""
        with self._lock:
            current_agents = len(self._agents)
            if current_agents < self.pool_size:
                needed = self.pool_size - current_agents
                for i in range(needed):
                    agent_type = self.agent_types[i % len(self.agent_types)]
                    self._create_agent(agent_type)
    
    def scale_up(self, count: int = 1):
        """Add more agents to the pool"""
        logger.info(f"Scaling up pool by {count} agents")
        for i in range(count):
            agent_type = self.agent_types[i % len(self.agent_types)]
            self._create_agent(agent_type)
    
    def scale_down(self, count: int = 1):
        """Remove idle agents from the pool"""
        with self._lock:
            removed = 0
            for agent_id in list(self._agents.keys()):
                if removed >= count:
                    break
                if agent_id not in self._busy_set:
                    self._remove_agent(agent_id)
                    removed += 1
        logger.info(f"Scaled down pool by {removed} agents")
    
    def get_stats(self) -> PoolStats:
        """Get current pool statistics"""
        with self._lock:
            idle = sum(1 for a in self._agents.values() if a.state == AgentState.IDLE)
            busy = len(self._busy_set)
            error = sum(1 for a in self._agents.values() if a.state == AgentState.ERROR)
            
            avg_duration = 0.0
            if self._task_durations:
                avg_duration = sum(self._task_durations) / len(self._task_durations)
            
            utilization = 0.0
            total = len(self._agents)
            if total > 0:
                utilization = busy / total
                
            return PoolStats(
                total_agents=total,
                idle_agents=idle,
                busy_agents=busy,
                error_agents=error,
                total_tasks_completed=self._total_tasks_completed,
                total_errors=self._total_errors,
                avg_task_duration=avg_duration,
                pool_utilization=utilization,
            )
    
    def get_agent_details(self) -> List[Dict[str, Any]]:
        """Get details for all agents in the pool"""
        with self._lock:
            return [
                {
                    "agent_id": a.agent_id,
                    "agent_type": a.agent_type,
                    "state": a.state.value,
                    "task_count": a.task_count,
                    "error_count": a.error_count,
                    "age_seconds": a.age_seconds,
                    "idle_time": a.idle_time,
                    "current_task": a.current_task_id,
                }
                for a in self._agents.values()
            ]
    
    def shutdown(self):
        """Shutdown the pool and cleanup all agents"""
        logger.info("Shutting down agent pool")
        self._shutdown.set()
        
        with self._lock:
            agent_ids = list(self._agents.keys())
            for agent_id in agent_ids:
                self._remove_agent(agent_id)
        
        self._maintenance_thread.join(timeout=5.0)


if __name__ == "__main__":
    import random
    
    logging.basicConfig(level=logging.INFO)
    
    # Demo usage
    pool = SubagentPool(
        pool_size=3,
        agent_types=["backend", "frontend", "data"],
        warmup_on_init=True,
    )
    
    print("\n=== Initial Pool Stats ===")
    stats = pool.get_stats()
    print(f"Total agents: {stats.total_agents}")
    print(f"Idle agents: {stats.idle_agents}")
    
    # Simulate some work
    def simulate_task(agent: SubagentInstance):
        print(f"Agent {agent.agent_id} working...")
        time.sleep(random.uniform(0.5, 1.0))
        return f"Result from {agent.agent_id}"
    
    # Use context manager
    for i in range(5):
        with pool.get_agent() as agent:
            result = simulate_task(agent)
            print(f"Task {i}: {result}")
    
    print("\n=== Final Pool Stats ===")
    stats = pool.get_stats()
    print(f"Total agents: {stats.total_agents}")
    print(f"Tasks completed: {stats.total_tasks_completed}")
    print(f"Avg task duration: {stats.avg_task_duration:.2f}s")
    
    pool.shutdown()
