"""
Common exception types and error handling utilities
"""

from typing import Any, Callable
import logging
import functools

logger = logging.getLogger(__name__)


class OrchestratorError(Exception):
    """Base exception for orchestrator errors"""

    pass


class TaskError(OrchestratorError):
    """Task-related errors"""

    pass


class AgentError(OrchestratorError):
    """Agent-related errors"""

    pass


class ConfigError(OrchestratorError):
    """Configuration-related errors"""

    pass


class ValidationError(OrchestratorError):
    """Input validation errors"""

    pass


def safe_execute(
    func: Callable, default: Any = None, error_types: tuple = (Exception,)
) -> Any:
    """
    Safely execute a function, returning default on error

    Args:
        func: Function to execute
        default: Default value to return on error
        error_types: Tuple of exception types to catch

    Returns:
        Function result or default value
    """
    try:
        return func()
    except error_types as e:
        logger.warning(f"Safe execute failed: {e}")
        return default


def with_error_handling(default_return=None, log_errors=True):
    """
    Decorator for consistent error handling

    Args:
        default_return: Value to return on error
        log_errors: Whether to log errors
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}")
                return default_return

        return wrapper

    return decorator


def validate_not_empty(value: str, field_name: str) -> str:
    """Validate that a string field is not empty"""
    if not value or not value.strip():
        raise ValidationError(f"{field_name} cannot be empty")
    return value.strip()


def validate_positive_int(value: int, field_name: str) -> int:
    """Validate that an integer is positive"""
    if value <= 0:
        raise ValidationError(f"{field_name} must be positive")
    return value
