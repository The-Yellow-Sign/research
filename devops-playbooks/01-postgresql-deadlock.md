---
title: "PostgreSQL: Deadlock Detected"
service: postgres
severity: critical
error_codes: [40P01, DEADLOCK_DETECTED, 0x8004]
tags: [database, postgresql, deadlock, transaction, concurrency]
---

# PostgreSQL: Deadlock Detected

## Симптомы

Пользователи наблюдают резкое увеличение времени отклика приложения или полное зависание транзакций. В логах появляются ошибки о взаимной блокировке (deadlock). Некоторые запросы зависают на минуты, после чего откатываются с ошибкой. В monitoring дашбордах видно резкий рост числа активных соединений и заблокированных транзакций. Веб-приложение может возвращать 504 Gateway Timeout или Internal Server Error (500).

## Логи и Сообщения об ошибках

```text
2025-11-28 14:32:18.742 UTC [47823] user_service@prod_db ERROR:  deadlock detected
2025-11-28 14:32:18.742 UTC [47823] user_service@prod_db DETAIL:  Process 47823 waits for ShareLock on transaction 89234512; blocked by process 47891.
        Process 47891 waits for ShareLock on transaction 89234487; blocked by process 47823.
2025-11-28 14:32:18.742 UTC [47823] user_service@prod_db HINT:  See server log for query details.
2025-11-28 14:32:18.742 UTC [47823] user_service@prod_db CONTEXT:  while updating tuple (0,127) in relation "user_accounts"
2025-11-28 14:32:18.742 UTC [47823] user_service@prod_db STATEMENT:  UPDATE user_accounts SET balance = balance - 100.00 WHERE user_id = 'USR-9284719' AND account_status = 'active'
```

```text
2025-11-28 14:35:42.129 UTC [48012] payment_worker@prod_db ERROR:  40P01: deadlock detected
2025-11-28 14:35:42.129 UTC [48012] payment_worker@prod_db LOCATION:  DeadLockReport, deadlock.c:1140
2025-11-28 14:35:42.130 UTC [48012] payment_worker@prod_db STATEMENT:  
        BEGIN;
        UPDATE orders SET status = 'processing', updated_at = NOW() WHERE order_id = 'ORD-88247123';
        INSERT INTO audit_log (order_id, action, timestamp) VALUES ('ORD-88247123', 'status_change', NOW());
        COMMIT;
FATAL: terminating connection due to administrator command
server closed the connection unexpectedly
        This probably means the server terminated abnormally
        before or while processing the request.
```

```text
[2025-11-28T14:38:15.834Z] WARN  [pool-7-thread-42] c.m.s.DatabaseTransactionManager - Transaction rollback initiated
org.postgresql.util.PSQLException: ERROR: deadlock detected
  Detail: Process 49127 waits for ExclusiveLock on tuple (12,94) of relation 16401 of database 16384; blocked by process 49156.
Process 49156 waits for ExclusiveLock on tuple (12,88) of relation 16401 of database 16384; blocked by process 49127.
        at org.postgresql.core.v3.QueryExecutorImpl.receiveErrorResponse(QueryExecutorImpl.java:2553)
        at org.postgresql.core.v3.QueryExecutorImpl.processResults(QueryExecutorImpl.java:2285)
        at org.postgresql.core.v3.QueryExecutorImpl.execute(QueryExecutorImpl.java:323)
        at org.postgresql.jdbc.PgStatement.executeInternal(PgStatement.java:473)
        at org.postgresql.jdbc.PgStatement.execute(PgStatement.java:393)
        at com.mycompany.service.PaymentProcessor.processTransfer(PaymentProcessor.java:156)
        at com.mycompany.service.PaymentProcessor$$FastClassBySpringCGLIB$$a8bc1234.invoke(<generated>)
SQLState: 40P01
ErrorCode: 0
Thread ID: pool-7-thread-42
Request UUID: 7f3a9c12-8d44-4f2b-9a1e-3c8b4d7e2f91
```

## Диагностика

Проверьте текущие блокировки в базе данных:

```bash
# Подключитесь к PostgreSQL
psql -U postgres -d prod_db

# Проверьте активные блокировки
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement,
    blocked_activity.application_name AS blocked_application,
    blocking_activity.application_name AS blocking_application
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

```bash
# Проверьте статистику дедлоков
SELECT datname, deadlocks 
FROM pg_stat_database 
WHERE datname = 'prod_db';

# Посмотрите долгие транзакции
SELECT pid, age(clock_timestamp(), xact_start), usename, state, query 
FROM pg_stat_activity 
WHERE state != 'idle' 
ORDER BY age DESC 
LIMIT 10;
```

```bash
# Включите логирование дедлоков для детального анализа
# В postgresql.conf
grep -E "deadlock_timeout|log_lock_waits" /etc/postgresql/14/main/postgresql.conf

# Проверьте pg_locks для анализа текущих локов
SELECT locktype, database, relation::regclass, page, tuple, virtualxid, 
       transactionid, mode, granted, pid
FROM pg_locks
WHERE NOT granted
ORDER BY pid;
```

## Решение

**Шаг 1: Немедленное устранение блокировки (если критично)**

```bash
# Найдите PID блокирующего процесса
SELECT pg_terminate_backend(blocking_pid);
# Замените blocking_pid на конкретный PID из диагностики

# Если pg_terminate_backend не помогает, используйте более жесткий метод:
SELECT pg_cancel_backend(blocking_pid);
```

**Шаг 2: Анализ кода приложения**

Найдите в коде места, где происходят UPDATE/INSERT в неоптимальном порядке:

```bash
# Проверьте логи приложения на наличие паттернов
grep -r "UPDATE.*WHERE.*=" app_logs/application-$(date +%Y-%m-%d).log | grep -E "user_accounts|orders"
```

Типичные причины дедлоков:
- Разный порядок обновления строк в разных транзакциях
- Длинные транзакции с множественными UPDATE
- Отсутствие индексов на WHERE условиях

**Шаг 3: Рефакторинг транзакций**

Перепишите код с соблюдением строгого порядка блокировок:

```sql
-- Плохо (может вызвать deadlock):
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 2;
UPDATE accounts SET balance = balance + 100 WHERE id = 1;
COMMIT;

-- Хорошо (всегда обновляем в порядке возрастания ID):
BEGIN;
UPDATE accounts SET balance = balance + 100 WHERE id = 1;
UPDATE accounts SET balance = balance - 100 WHERE id = 2;
COMMIT;

-- Или используйте FOR UPDATE с сортировкой:
BEGIN;
SELECT * FROM accounts WHERE id IN (1, 2) ORDER BY id FOR UPDATE;
-- затем UPDATE
COMMIT;
```

**Шаг 4: Настройка PostgreSQL для лучшего детектирования**

```bash
# Отредактируйте postgresql.conf
sudo nano /etc/postgresql/14/main/postgresql.conf

# Добавьте/измените:
deadlock_timeout = 1s                    # Быстрее детектировать дедлоки
log_lock_waits = on                      # Логировать долгие ожидания
lock_timeout = 10s                       # Таймаут на получение лока
statement_timeout = 30s                  # Общий таймаут запроса

# Перезагрузите конфигурацию
sudo systemctl reload postgresql
# или
SELECT pg_reload_conf();
```

**Шаг 5: Мониторинг и профилактика**

```bash
# Создайте алерт в Prometheus/Grafana:
# rate(pg_stat_database_deadlocks[5m]) > 0

# Добавьте скрипт проверки в cron
cat > /usr/local/bin/check_pg_deadlocks.sh << 'EOF'
#!/bin/bash
DEADLOCKS=$(psql -U postgres -d prod_db -t -c "SELECT deadlocks FROM pg_stat_database WHERE datname='prod_db';")
if [ "$DEADLOCKS" -gt 10 ]; then
    echo "WARNING: Deadlocks detected: $DEADLOCKS" | mail -s "PostgreSQL Deadlock Alert" ops@company.com
fi
EOF

chmod +x /usr/local/bin/check_pg_deadlocks.sh
echo "*/5 * * * * /usr/local/bin/check_pg_deadlocks.sh" | crontab -
```

**Шаг 6: Код-ревью и best practices**

- Держите транзакции короткими
- Используйте REPEATABLE READ или SERIALIZABLE изоляцию осознанно
- Всегда блокируйте ресурсы в одном и том же порядке
- Добавьте retry logic с exponential backoff в приложении:

```python
# Пример на Python
import psycopg2
import time

def execute_with_retry(query, max_retries=3):
    for attempt in range(max_retries):
        try:
            conn = psycopg2.connect(...)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            return True
        except psycopg2.extensions.TransactionRollbackError as e:
            if "deadlock detected" in str(e):
                time.sleep(2 ** attempt)  # exponential backoff
                continue
            raise
    return False
```
