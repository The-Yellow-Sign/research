---
service: postgresql
title: "Инцидент #2025-12-28: Массовый отказ соединений с БД в кластере EKS"
tags: [post-mortem, postgres, k8s, down-time]
severity: critical
---

## Краткое описание
28 декабря 2024 года с 14:15 по 15:40 MSK наблюдалась полная недоступность основного инстанса PostgreSQL в кластере Kubernetes (EKS). Это привело к невозможности обработки платежей и авторизации пользователей.

## Хронология событий (Timeline)

- **14:15** — Сработал алерт `PostgresHighConnectionCount` в Grafana.
- **14:20** — Первые жалобы от пользователей на ошибки 500 и "Connection limit reached".
- **14:25** — On-call инженер попытался зайти в контейнер с БД, но получил Connection Timeout.
- **14:35** — Выявлено, что один из микросервисов (`billing-service`) начал бесконечно пересоздавать коннекты из-за бага в новой версии.
- **15:00** — Принято решение об откате `billing-service` до предыдущей стабильной версии.
- **15:30** — Нагрузка на БД начала нормализоваться.
- **15:40** — Сервис полностью восстановлен.

## Технический анализ
Проблема возникла из-за отсутствия лимитов на количество соединений на стороне приложения и неправильной настройки `max_connections` в PostgreSQL.

### Логи из пода PostgreSQL:
```text
2025-12-28 14:18:22.123 UTC [1] FATAL:  remaining connection slots are reserved for non-replication superuser connections
2025-12-28 14:18:22.456 UTC [452] ERROR:  connection limit exceeded for group "app_users"
2025-12-28 14:19:01.999 UTC [12] LOG:  checkpointer: checkpoint starting: xlog
```

### Stacktrace клиентского приложения (Java/Spring):
```java
org.postgresql.util.PSQLException: FATAL: remaining connection slots are reserved for non-replication superuser connections
    at org.postgresql.core.v3.ConnectionFactoryImpl.doAuthentication(ConnectionFactoryImpl.java:525)
    at org.postgresql.core.v3.ConnectionFactoryImpl.openConnectionImpl(ConnectionFactoryImpl.java:208)
    at org.postgresql.driver.Connection(Driver.java:222)
    at com.zaxxer.hikari.pool.PoolBase.newConnection(PoolBase.java:358)
    at com.zaxxer.hikari.pool.PoolBase.newPoolEntry(PoolBase.java:206)
```

## Корневые причины (Root Causes)
1. **Баг в приложении**: В релизе `v2.4.1` сервиса биллинга был пропущен параметр `maximumPoolSize` в HikariCP, что привело к неограниченному росту пула.
2. **Недостаточный мониторинг**: Алерт сработал слишком поздно, когда пул уже был исчерпан.
3. **Отсутствие PGBouncer**: Прямые подключения к инстансу делают систему уязвимой к подобным лавинообразным атакам.

## Дальнейшие действия (Action Items)
- [ ] Внедрить PGBouncer как sidecar или отдельный Deployment в K8s.
- [ ] Обновить алертинг, добавив порог в 80% от max_connections.
- [ ] Провести аудит всех конфигов пулов соединений в микросервисах.

> ⚠️ WARNING: Не увеличивайте `max_connections` без предварительной настройки параметров памяти `shared_buffers`, иначе БД может уйти в OOM.
