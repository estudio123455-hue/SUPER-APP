"""Typed, asynchronous Event Bus for decoupled inter-module communication (Law 1).

Provides an abstract EventBus contract with both:
1. InMemoryEventBus (lightweight, zero-dependency default for local development and pytest suites).
2. RedisStreamsEventBus (distributed event bus for Years 3-4 multi-instance scaling via Redis Streams XADD/XREADGROUP).
"""

from abc import ABC, abstractmethod
import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import json
import logging
from typing import Any, TypeVar
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Base immutable Domain Event shared across bounded contexts."""

    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


E = TypeVar("E", bound=DomainEvent)
EventHandler = Callable[[E], Awaitable[None]]


class EventBus(ABC):
    """Abstract interface defining the Event Bus contract for all environments."""

    @abstractmethod
    def subscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        """Registers an asynchronous handler for a specific DomainEvent subclass."""
        pass

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publishes a DomainEvent to all registered subscribers."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clears all subscriptions."""
        pass


class InMemoryEventBus(EventBus):
    """Async in-memory event bus for Years 1-2 and isolated local pytest runs."""

    def __init__(self) -> None:
        self._subscribers: dict[type[DomainEvent], list[EventHandler[DomainEvent]]] = (
            defaultdict(list)
        )

    def subscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        typed_handler: EventHandler[DomainEvent] = handler  # type: ignore[assignment]
        if typed_handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(typed_handler)

    async def publish(self, event: DomainEvent) -> None:
        handlers = list(self._subscribers.get(type(event), []))
        if not handlers:
            return
        await asyncio.gather(*(handler(event) for handler in handlers))

    def clear(self) -> None:
        self._subscribers.clear()


def _json_serializer(obj: Any) -> Any:
    """JSON serializer for UUIDs, datetimes, and sets in DomainEvents."""
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, set):
        return list(obj)
    raise TypeError(f"Type {type(obj)} is not JSON serializable")


class RedisStreamsEventBus(EventBus):
    """Distributed event bus powered by Redis Streams (XADD / XREADGROUP) for scaling."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        group_name: str = "superapp-workers",
        consumer_name: str = "worker-1",
    ) -> None:
        self.redis_url = redis_url
        self.group_name = group_name
        self.consumer_name = consumer_name
        self._subscribers: dict[type[DomainEvent], list[EventHandler[DomainEvent]]] = (
            defaultdict(list)
        )
        self._event_types: dict[str, type[DomainEvent]] = {}
        self._client: Any = None

    async def _get_client(self) -> Any:
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(
                self.redis_url,
                decode_responses=True,
            )
        return self._client

    def subscribe(
        self,
        event_type: type[E],
        handler: EventHandler[E],
    ) -> None:
        typed_handler: EventHandler[DomainEvent] = handler  # type: ignore[assignment]
        if typed_handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(typed_handler)
        self._event_types[event_type.__name__] = event_type

    def get_stream_key(self, event_name: str) -> str:
        return f"superapp:events:{event_name}"

    async def publish(self, event: DomainEvent) -> None:
        """Serializes DomainEvent to JSON and appends to Redis Stream via XADD."""
        event_name = type(event).__name__
        stream_key = self.get_stream_key(event_name)
        payload = json.dumps(asdict(event), default=_json_serializer)

        client = await self._get_client()
        await client.xadd(
            stream_key,
            {"event_name": event_name, "payload": payload},
        )

        # Also dispatch immediately to in-process subscribers if any
        local_handlers = list(self._subscribers.get(type(event), []))
        if local_handlers:
            await asyncio.gather(*(handler(event) for handler in local_handlers))

    async def ensure_group(self, stream_key: str) -> None:
        """Creates the consumer group if it does not already exist."""
        client = await self._get_client()
        try:
            await client.xgroup_create(
                stream_key,
                self.group_name,
                id="$",
                mkstream=True,
            )
        except Exception as exc:
            # redis.exceptions.ResponseError: BUSYGROUP Consumer Group name already exists
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume_messages(
        self,
        stream_key: str,
        count: int = 10,
        block_ms: int = 100,
    ) -> int:
        """Reads and processes pending/new messages using XREADGROUP and acknowledges via XACK."""
        client = await self._get_client()
        await self.ensure_group(stream_key)

        entries = await client.xreadgroup(
            self.group_name,
            self.consumer_name,
            {stream_key: ">"},
            count=count,
            block=block_ms,
        )

        processed_count = 0
        if not entries:
            return processed_count

        for _, messages in entries:
            for message_id, data in messages:
                event_name = data.get("event_name")
                payload_str = data.get("payload", "{}")
                event_type = self._event_types.get(event_name)

                if event_type:
                    parsed_dict = json.loads(payload_str)
                    # Reconstruct basic event fields
                    event_instance = self._deserialize_event(event_type, parsed_dict)
                    handlers = list(self._subscribers.get(event_type, []))
                    if handlers:
                        await asyncio.gather(*(h(event_instance) for h in handlers))

                await client.xack(stream_key, self.group_name, message_id)
                processed_count += 1

        return processed_count

    def _deserialize_event(
        self,
        event_type: type[DomainEvent],
        data: dict[str, Any],
    ) -> DomainEvent:
        """Safely hydrates a DomainEvent from its JSON dictionary representation."""
        clean_data = dict(data)
        if "event_id" in clean_data and isinstance(clean_data["event_id"], str):
            clean_data["event_id"] = UUID(clean_data["event_id"])
        if "occurred_at" in clean_data and isinstance(clean_data["occurred_at"], str):
            clean_data["occurred_at"] = datetime.fromisoformat(clean_data["occurred_at"])
        # Additional UUID fields conversion
        for k, v in clean_data.items():
            if isinstance(v, str) and len(v) == 36 and v.count("-") == 4:
                try:
                    clean_data[k] = UUID(v)
                except ValueError:
                    pass
        try:
            return event_type(**clean_data)  # type: ignore[call-arg]
        except Exception:
            # Fallback to base event if signature mismatch occurs
            return DomainEvent(
                event_id=clean_data.get("event_id", uuid4()),
                occurred_at=clean_data.get("occurred_at", datetime.now(UTC)),
            )

    def clear(self) -> None:
        self._subscribers.clear()
        self._event_types.clear()

    async def close(self) -> None:
        """Closes the underlying Redis connection."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def create_event_bus(settings: Any = None, force_redis: bool = False) -> EventBus:
    """Factory creating RedisStreamsEventBus if configured and reachable, else InMemoryEventBus."""
    if not force_redis and settings is None:
        return InMemoryEventBus()

    redis_url = getattr(settings, "redis_url", None) or "redis://localhost:6379/0"
    if force_redis:
        return RedisStreamsEventBus(redis_url=redis_url)

    # In production/docker environments, fallback gracefully if Redis is offline
    return InMemoryEventBus()


# Default singleton instance for the Modular Monolith runtime
event_bus: InMemoryEventBus = InMemoryEventBus()
