---
service: RabbitMQ, Java
title: RabbitMQ Internal Integration API (v1)
tags: api, messaging, rabbitmq, java
severity: low
---

# Internal Event Bus API Specification

Documentation for internal Java services interacting with the core Message Broker.

## Endpoints (Internal REST Wrapper)

| Method | Path | Description | Payload |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/publish` | Отправка сообщения в exchange | `MessageDTO` |
| `GET` | `/api/v1/queues/{name}` | Статус конкретной очереди | - |

## Example Request (Java client)

```java
@PostMapping("/publish")
public ResponseEntity<String> sendMessage(@RequestBody EventMessage message) {
    rabbitTemplate.convertAndSend("exchange_name", "routing_key", message);
    return ResponseEntity.ok("Sent");
}
```

## JSON Schema Example
```json
{
  "event_id": "uuid",
  "payload": {
    "user_id": 12345,
    "action": "LOGIN_SUCCESS"
  },
  "metadata": {
    "source": "auth-service"
  }
}
```

## Note on Retries
We use Dead Letter Exchanges (DLX) for failed messages. If consumer returns `NACK`, message goes to `retry-queue` with TTL.

> [!IMPORTANT]
> All published messages must have `correlation_id` header for tracing (Jaeger).
