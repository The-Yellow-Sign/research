---
title: "Elasticsearch: Cluster Health RED"
service: elasticsearch
severity: critical
error_codes: [cluster_red, shard_failed, unassigned_shards]
tags: [elasticsearch, cluster, shards, search, distributed]
---

# Elasticsearch: Cluster Health RED

## Симптомы

Elasticsearch cluster health показывает RED status. Поиск возвращает partial results или ошибки. Index операции могут падать. Kibana отображает предупреждение о проблемах с кластером. Некоторые данные недоступны. Monitoring показывает unassigned shards.

## Логи и Сообщения об ошибках

```text
[2025-11-28T16:42:18,392][WARN ][o.e.c.r.a.AllocationService] [es-node-1] failed to allocate shard
[logs-2025.11.28][0], node[null], [R], recovery_source[peer recovery], s[UNASSIGNED], unassigned_info[[reason=CLUSTER_RECOVERED], at[2025-11-28T16:42:18.392Z]]
[2025-11-28T16:42:18,718][ERROR][o.e.i.e.Engine           ] [es-node-1] [logs-2025.11.28][1] failed engine
org.elasticsearch.index.engine.EngineException: shard failed
Caused by: java.io.IOException: No space left on device
Cluster UUID: a8f3c924-b871-4e9f-2a6c-3b8d7e5f1a0c
Node: es-node-1 (10.0.1.10)
Status: RED
Active shards: 245/300
Unassigned shards: 55
```

```text
{"type": "server", "timestamp": "2025-11-28T16:44:47.192Z", "level": "ERROR", "component": "o.e.c.s.ClusterApplierService", "cluster.name": "prod-cluster", "node.name": "es-node-2", "message": "failed to apply cluster state", "cluster.uuid": "a8f3c924", "node.id": "H8f3c924"}
org.elasticsearch.cluster.coordination.FailedToCommitClusterStateException: timed out while waiting for cluster state to be committed
Primary shard [logs-2025.11.28][0] is unassigned
Replica shard [logs-2025.11.28][1] not found on any node
Disk watermark exceeded: 95% used
Failed allocation attempts: 5
```

```text
[2025-11-28 16:47:33] WARN  org.elasticsearch.cluster.routing.UnassignedInfo
[logs-2025.11.28][0] failed to create shard, not enough master nodes
ElasticsearchException[failed to create shard]
Caused by: NotMasterException[node not master]
Available master nodes: 1
Required master nodes: 2
Cluster name: prod-cluster
Exit status: cluster_red
Unassigned reason: NODE_LEFT
Index: logs-2025.11.28
Shard: 0
Recovery attempt: 3
```

## Диагностика

```bash
# Проверьте cluster health
curl -X GET "localhost:9200/_cluster/health?pretty"
curl -X GET "localhost:9200/_cat/health?v"

# Найдите unassigned shards
curl -X GET "localhost:9200/_cat/shards?v" | grep UNASSIGNED

# Проверьте allocation explain
curl -X GET "localhost:9200/_cluster/allocation/explain?pretty"

# Проверьте disk space
curl -X GET "localhost:9200/_cat/allocation?v"
df -h
```

## Решение

**Шаг 1:** Найдите причину

```bash
curl -X GET "localhost:9200/_cluster/allocation/explain?pretty" \
  -H 'Content-Type: application/json' -d'
{
  "index": "logs-2025.11.28",
  "shard": 0,
  "primary": true
}'
```

**Шаг 2:** Освободите место

```bash
# Удалите старые индексы
curl -X DELETE "localhost:9200/logs-2025.10.*"

# Включите auto-delete через ILM
curl -X PUT "localhost:9200/_ilm/policy/logs_policy" -H 'Content-Type: application/json' -d'
{
  "policy": {
    "phases": {
      "delete": {
        "min_age": "30d",
        "actions": {"delete": {}}
      }
    }
  }
}'
```

**Шаг 3:** Переназначьте shards

```bash
curl -X POST "localhost:9200/_cluster/reroute?retry_failed=true"
```
