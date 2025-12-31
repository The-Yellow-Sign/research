---
service: AWS EKS, Redis
title: Post-mortem: Утечка соединений Redis в кластере EKS
tags: incident, redis, eks, networking
severity: high
---

# Разбор инцидента: Массовый отказ сервиса "Order-Service" из-за лимита соединений Redis

**Дата:** 2025-10-15
**Длительность:** 45 минут (14:15 - 15:00 MSK)
**Участники:** @ivanov, @petrov (On-call SRE)

## Описание
Начиная с 14:15 начали поступать алерты о деградации "Order-Service". Пользователи видели 503 ошибку. Причина — исчерпание пула соединений в Redis.

## Таймлайн
- **14:15** — Первый алерт `RedisMaxConnectionsReached`.
- **14:20** — SRE обнаружили рост количества ESTABLISHED соединений с нод EKS в сторону Managed Redis.
- **14:35** — Выяснено, что после деплоя версии `v1.2.4` не закрываются соединения в Go-клиенте.
- **15:00** — Откат на `v1.2.3`, восстановление работы.

## Технические подробности

### Стык логов сервиса:
```bash
2025-10-15T14:16:02Z ERROR Order-Service: could not get redis connection: pool exhausted
2025-10-15T14:16:05Z WARN Order-Service: retrying connection (attempt 3)...
```

### Метрики
| Параметр | Значение в пике | Лимит |
| :--- | :--- | :--- |
| Active Connections | 65,000 | 65,000 |
| CPU Load Redis | 12% | 80% |
| Memory Usage | 4.2GB | 16GB |

## Причины (Root Cause)
Ошибка в логике `defer conn.Close()` внутри middleware для распределенных локов. Код выходил по таймауту до того, как срабатывал дефер в некоторых ситуациях.

## Резюме
1. Добавить лимиты на уровне sidecar-прокси.
2. Провести Code Review всех вызовов Redis в "Order-Service".
3. Настроить авто-киллинг Idle-соединений на стороне сервера Redis.

> [!IMPORTANT]
> Всем разработчикам проверить конфигурации `IdleTimeout` в своих Redis клиентах.
