---
title: "MySQL: Too Many Connections"
service: mysql
severity: critical
error_codes: [1040, ER_CON_COUNT_ERROR, HY000]
tags: [mysql, database, connections, pool, concurrency]
---

# MySQL: Too Many Connections

## Симптомы

Приложение не может подключиться к MySQL, возвращает ошибку "Too many connections". Новые пользователи не могут войти в систему. Существующие сессии могут работать нормально, но новые запросы зависают. В логах приложения много connection timeout errors. Monitoring показывает 100% использование max_connections.

## Логи и Сообщения об ошибках

```text
2025-11-28 16:15:42 [ERROR] /usr/sbin/mysqld: ERROR 1040 (HY000): Too many connections
2025-11-28 16:15:42 [Warning] IP address '10.0.2.47' could not be resolved: Temporary failure in name resolution
2025-11-28 16:15:42 [Warning] Aborted connection 15821 to db: 'prod_app' user: 'app_user' host: '10.0.2.47' (Got timeout reading communication packets)
2025-11-28 16:15:43 [ERROR] Error in accept: Too many open files
Thread ID: 15821
Process list count: 151/151 (max_connections reached)
Active connections by user:
  app_user: 127
  monitoring: 15
  admin: 9
Time: 2025-11-28T16:15:42.847Z
```

```text
[2025-11-28 16:17:19.284] ERROR com.mysql.cj.jdbc.exceptions.MySQLNonTransientConnectionException
Unable to create connection to database server. Too many connections
	at com.mysql.cj.jdbc.ConnectionImpl.createNewIO(ConnectionImpl.java:834)
SQLException: com.mysql.cj.exceptions.CJCommunicationsException: Communications link failure
SQLState: 08S01
ErrorCode: 1040
Connection URL: jdbc:mysql://10.0.1.10:3306/prod_app
Max pool size: 50
Active connections: 50
Idle connections: 0
Waiting threads: 127
Request ID: a8f3c924-b871-4e9f-2a6c
Thread: http-nio-8080-exec-42
```

```text
pymysql.err.OperationalError: (1040, 'Too many connections')
During handling of the above exception, another exception occurred:
Traceback (most recent call last):
  File "/app/database/connection.py", line 89, in get_connection
    conn = pymysql.connect(host='10.0.1.10', user='app_user', password='***', database='prod_app')
  File "/usr/local/lib/python3.11/site-packages/pymysql/connections.py", line 353, in __init__
    self.connect()
  File "/usr/local/lib/python3.11/site-packages/pymysql/connections.py", line 633, in connect
    raise exc
pymysql.err.OperationalError: (1040, 'Too many connections')
DateTime: 2025-11-28 16:18:47
Max connections configured: 151
Current connections: 151
Failed connection attempts (last minute): 847
Application: payment-service
PID: 18293
```

## Диагностика

```bash
# Подключитесь к MySQL
mysql -u root -p

# Проверьте текущее количество подключений
SHOW STATUS LIKE 'Threads_connected';
SHOW STATUS LIKE 'Max_used_connections';
SHOW VARIABLES LIKE 'max_connections';

# Посмотрите активные процессы
SHOW FULL PROCESSLIST;

# Груприруйте по пользователям
SELECT user, COUNT(*) as connections 
FROM information_schema.processlist 
GROUP BY user 
ORDER BY connections DESC;

# Найдите долгие запросы
SELECT * FROM information_schema.processlist 
WHERE time > 60 
ORDER BY time DESC;
```

## Решение

**Шаг 1:** Увеличьте max_connections

```bash
mysql -u root -p
SET GLOBAL max_connections = 500;

# Permanently
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf
# Добавьте:
max_connections = 500
wait_timeout = 600
interactive_timeout = 600

sudo systemctl restart mysql
```

**Шаг 2:** Убейте зависшие соединения

```bash
# Найдите и убейте спящие соединения
mysql -u root -p -e "
SELECT CONCAT('KILL ', id, ';') 
FROM information_schema.processlist 
WHERE command = 'Sleep' 
AND time > 300 
INTO OUTFILE '/tmp/kill_queries.sql';"

mysql -u root -p < /tmp/kill_queries.sql
```

**Шаг 3:** Оптимизируйте connection pooling

```python
# Правильная настройка пула
pool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="mypool",
    pool_size=10,  # НЕ 100!
    pool_reset_session=True,
    host='10.0.1.10',
    database='prod_app'
)
```
