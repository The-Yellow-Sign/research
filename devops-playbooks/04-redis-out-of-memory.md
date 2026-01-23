---
title: "Redis: Out of Memory (OOM)"
service: redis
severity: critical
error_codes: [OOM, ERR_MAXMEMORY, ENOMEM]
tags: [redis, cache, memory, oom, eviction]
---

# Redis: Out of Memory (OOM)

## Симптомы

Приложение не может записать данные в Redis, получает ошибки "OOM command not allowed". Кэш перестает обновляться, увеличивается нагрузка на БД. Операции SET, LPUSH завершаются с ошибкой, но READ работают. Мониторинг показывает 100% использование maxmemory.

## Логи и Сообщения об ошибках

```text
18472:M 28 Nov 2025 15:32:18.392 # WARNING: Memory usage reached 99.8% of maxmemory limit
18472:M 28 Nov 2025 15:32:18.412 # WARNING: 847 keys evicted in the last second
18472:M 28 Nov 2025 15:32:24.718 # WARNING: Unable to free memory by evicting keys
18472:M 28 Nov 2025 15:32:24.719 # OOM command not allowed when used memory > 'maxmemory'
Redis version: 7.0.12
Used memory: 4.29G (4294967296 bytes)
Maxmemory: 4.00G (4000000000 bytes)
Eviction policy: noeviction
Keys: 13847291
Client addr=10.0.1.47:52183 cmd=SET
```

```text
2025-11-28T15:34:47.192Z ERROR [redis-client] Command execution failed
redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'.
  File "/app/cache/redis_wrapper.py", line 147, in set_with_expiry
    self.client.setex(key, ttl, json.dumps(value))
redis.exceptions.ResponseError: OOM command not allowed
Request ID: c8f2a9e1-7d4b-4c2f-9a1e-8b3c7d2e4f91
Key: user:session:USR-9284719
Operation: SETEX
Thread: worker-thread-23
```

```text
[2025-11-28 15:36:12.847] WARN JedisDataException: ERR max Memory reached
io.lettuce.core.RedisCommandExecutionException: OOM command not allowed
	at io.lettuce.core.protocol.AsyncCommand.completeResult(AsyncCommand.java:120)
	at com.company.cache.CacheService.storeUserData(CacheService.java:89)
Redis Info:
  used_memory_human: 4.00G
  maxmemory_human: 4.00G
  maxmemory_policy: noeviction
  evicted_keys: 0
Command: HMSET user:profile:8472938 name "John"
```

## Диагностика

```bash
redis-cli INFO memory
redis-cli INFO keyspace
redis-cli --bigkeys

# Проверьте TTL
redis-cli --scan | while read key; do
    redis-cli TTL "$key"
done | grep -- "-1" | wc -l
```

## Решение

**Шаг 1:** Временно увеличьте память

```bash
redis-cli CONFIG SET maxmemory 8gb
```

**Шаг 2:** Настройте eviction

```bash
redis-cli CONFIG SET maxmemory-policy allkeys-lru
sudo nano /etc/redis/redis.conf
# Добавьте:
maxmemory 8gb
maxmemory-policy allkeys-lru
sudo systemctl restart redis
```

**Шаг 3:** Установите TTL на ключи

```bash
redis-cli --scan | while read key; do
    redis-cli EXPIRE "$key" 86400
done
```
