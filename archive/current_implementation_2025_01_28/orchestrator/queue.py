from __future__ import annotations

import os

from redis import Redis
from rq import Queue

# Redis connection with enhanced configuration for persistence
_redis = Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    db=int(os.environ.get("REDIS_DB", 0)),
    password=os.environ.get("REDIS_PASSWORD", None),
    socket_keepalive=True,
    socket_keepalive_options={},
    health_check_interval=30,
)

# Task queue with persistence support
jobs_q = Queue("autodev", connection=_redis, default_timeout=3600)

# Additional queues for different priorities/types
priority_q = Queue("autodev-priority", connection=_redis, default_timeout=1800)
cli_session_q = Queue("autodev-cli", connection=_redis, default_timeout=7200)
