---
title: "MongoDB: Replica Set Not Syncing"
service: mongodb
severity: critical
error_codes: [replication_lag, secondary_behind, sync_failed]
tags: [mongodb, replication, replica-set, sync, database]
---

# MongoDB: Replica Set Not Syncing

## Симптомы

Secondary узлы MongoDB отстают от Primary. Replication lag растет. Чтение из secondary возвращает устаревшие данные. Monitoring показывает большую разницу в oplog. Secondary может быть в состоянии RECOVERING. Failover невозможен из-за несинхронизированных данных.

## Логи и Сообщения об ошибках

```text
2025-11-28T17:15:42.392+0000 W REPL [rsSync] oplog sync error: HostUnreachable: could not find member to sync from
2025-11-28T17:15:42.718+0000 I REPL [replication-47] Replication lag is 3847 seconds
2025-11-28T17:15:43.294+0000 E STORAGE [repl writer worker 8] WiredTiger error: disk full
Replica Set: rs0
Member: mongodb-secondary-1 (10.0.1.11:27017)
State: RECOVERING
Replication lag: 3847 seconds
Oplog size: 5GB
Oplog used: 98%
Last applied: 2025-11-28T16:10:15.294Z
```

```text
{"t":{"$date":"2025-11-28T17:18:19.284Z"},"s":"E","c":"REPL","id":21203,"ctx":"ReplBatcher","msg":"Failed to apply batch of operations","error":"WriteConflict: WriteConflict"}
{"t":{"$date":"2025-11-28T17:18:19.847Z"},"s":"W","c":"REPL","id":21234,"msg":"Slow operation on secondary","durationMillis":15000,"oplog":{"ts":{"$timestamp":{"t":1701182299,"i":42}}}}
Replica member: mongodb-secondary-2
Sync source: mongodb-primary (10.0.1.10:27017)
Operations behind: 284719
Estimated catch-up time: 3847 seconds
Network latency: 250ms
```

```text
MongoServerError: not master and slaveOk=false
  at Connection.sendCommand (/node_modules/mongodb/lib/connection.js:847)
  at /app/database/mongo_client.js:156
Replica set state:
  PRIMARY: mongodb-primary (10.0.1.10)
  SECONDARY: mongodb-secondary-1 (STALE - lag: 3800s)
  SECONDARY: mongodb-secondary-2 (RECOVERING)
Priority: 1
Votes: 1
Health: UP
Connection: mongodb://10.0.1.11:27017/?replicaSet=rs0
```

## Диагностика

```bash
# Подключитесь к MongoDB
mongo --host mongodb-primary:27017

# Проверьте статус replica set
rs.status()
rs.printReplicationInfo()
rs.printSlaveReplicationInfo()

# Проверьте replication lag
db.printSlaveReplicationInfo()
```

## Решение

**Шаг 1:** Проверьте connectivity

```bash
# На secondary
mongo --host mongodb-primary:27017 --eval "db.adminCommand('ping')"

# Проверьте network latency
ping mongodb-primary
```

**Шаг 2:** Увеличьте oplog

```javascript
use local
db.oplog.rs.stats().maxSize  // Текущий размер

// Измените размер (выполните на primary)
db.adminCommand({replSetResizeOplog: 1, size: 10240})  // 10GB
```

**Шаг 3:** Resync secondary

```bash
# Остановите mongod
sudo systemctl stop mongod

# Удалите данные
rm -rf /var/lib/mongodb/*

# Запустите
sudo systemctl start mongod

# Он автоматически начнет initial sync
```
