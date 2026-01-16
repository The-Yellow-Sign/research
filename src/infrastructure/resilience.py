"""Production resilience patterns: Circuit Breaker, Retry с exponential backoff.

Обеспечивает устойчивость к сбоям внешних сервисов.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from time import time
from typing import Any, ParamSpec, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.settings import settings

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


class CircuitState(Enum):
    """Состояния Circuit Breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Circuit Breaker для защиты от каскадных сбоев.

    Attributes:
        name: Имя circuit для логирования.
        failure_threshold: Количество ошибок для открытия circuit.
        recovery_timeout: Время до перехода в half-open (секунды).
        failure_count: Текущее количество ошибок.
        last_failure_time: Время последней ошибки.
        state: Текущее состояние circuit.

    """

    name: str
    failure_threshold: int = 3
    recovery_timeout: int = 30
    failure_count: int = field(default=0, init=False)
    last_failure_time: float = field(default=0.0, init=False)
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)

    def record_success(self) -> None:
        """Записывает успешный вызов."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Записывает неудачный вызов."""
        self.failure_count += 1
        self.last_failure_time = time()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                "Circuit '%s' открыт после %d ошибок",
                self.name,
                self.failure_count,
            )

    def can_execute(self) -> bool:
        """Проверяет, можно ли выполнить вызов."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time() - self.last_failure_time
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit '%s' переходит в half-open", self.name)
                return True
            return False

        return True


class CircuitOpenError(Exception):
    """Circuit breaker открыт."""

    def __init__(self, circuit_name: str) -> None:
        self.circuit_name = circuit_name
        super().__init__(f"Circuit '{circuit_name}' открыт, запрос отклонён")


_circuits: dict[str, CircuitBreaker] = {}


def get_circuit(name: str) -> CircuitBreaker:
    """Возвращает или создаёт Circuit Breaker по имени."""
    if name not in _circuits:
        _circuits[name] = CircuitBreaker(
            name=name,
            failure_threshold=settings.circuit_failure_threshold,
            recovery_timeout=settings.circuit_recovery_timeout,
        )
    return _circuits[name]


def with_circuit_breaker(
    circuit_name: str,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Декоратор Circuit Breaker для async-функций.

    Args:
        circuit_name: Имя circuit breaker.

    Returns:
        Декоратор функции.

    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            circuit = get_circuit(circuit_name)

            if not circuit.can_execute():
                raise CircuitOpenError(circuit_name)

            try:
                result = await func(*args, **kwargs)
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure()
                raise e

        return wrapper

    return decorator


async def retry_with_backoff(
    coro_func: Callable[[], Any],
    max_attempts: int = 3,
    min_wait: float = 0.5,
    max_wait: float = 10.0,
    retry_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Any:
    """Выполняет корутину с retry и exponential backoff.

    Args:
        coro_func: Функция, возвращающая корутину.
        max_attempts: Максимум попыток.
        min_wait: Минимальное время ожидания (секунды).
        max_wait: Максимальное время ожидания (секунды).
        retry_exceptions: Типы исключений для retry.

    Returns:
        Результат выполнения корутины.

    Raises:
        Исходное исключение после исчерпания попыток.

    """
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=min_wait, max=max_wait),
            retry=retry_if_exception_type(retry_exceptions),
            reraise=True,
        ):
            with attempt:
                return await coro_func()
    except RetryError:
        raise


async def run_with_timeout(
    coro: Any,
    timeout: float,
    error_message: str = "Операция превысила таймаут",
) -> Any:
    """Выполняет корутину с таймаутом.

    Args:
        coro: Корутина для выполнения.
        timeout: Таймаут в секундах.
        error_message: Сообщение об ошибке при таймауте.

    Returns:
        Результат выполнения корутины.

    Raises:
        TimeoutError: При превышении таймаута.

    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout)
    except asyncio.TimeoutError as e:
        raise TimeoutError(error_message) from e
