from __future__ import annotations
import os
from redis import Redis
from rq import Queue

_redis = Redis(host=os.environ.get("REDIS_HOST", "localhost"), port=int(os.environ.get("REDIS_PORT", 6379)))
jobs_q = Queue("autodev", connection=_redis)