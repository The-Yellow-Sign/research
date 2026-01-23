# Инцидент #2024-12-25: Падение ноды Elasticsearch из-за OutOfMemory (OOM)

## Краткое описание
25 декабря в 03:15 ночи одна из дата-нод кластера Elasticsearch ушла в Restart Loop. Причиной стало исчерпание Heap памяти JVM из-за выполнения "тяжелого" агрегационного запроса от аналитического сервиса.

## Хронология
- **03:10** — Рост `jvm.mem.heap_used_percent` до 98% на ноде `es-data-03`.
- **03:12** — Появление ошибок `503 Service Unavailable` в Kibana.
- **03:15** — Node `es-data-03` упала. Сработал `systemd` рестарт, но нода не смогла подняться.
- **03:30** — Дежурный инженер увеличил лимиты памяти в K8s манифесте.

## Технический анализ (Logs)

### Лог из `/var/log/elasticsearch/cluster.log`:
```text
[2024-12-25T03:14:55,123][ERROR][o.e.b.ElasticsearchUncaughtExceptionHandler] [es-data-03] fatal error in thread [Thread-42], exiting
java.lang.OutOfMemoryError: Java heap space
    at org.apache.lucene.util.BytesRefHash.add(BytesRefHash.java:274) ~[lucene-core-8.11.1.jar:8.11.1]
    at org.elasticsearch.search.aggregations.bucket.terms.TermsAggregatorFactory$ExecutionMode$2.create(TermsAggregatorFactory.java:95) ~[elasticsearch-7.17.3.jar:7.17.3]
```

### Stacktrace JVM:
```text
Exception in thread "elasticsearch[es-data-03][search][T#4]" java.lang.OutOfMemoryError: Java heap space
   at org.elasticsearch.common.util.BigArrays.newLongArray(BigArrays.java:543)
   at org.elasticsearch.search.aggregations.bucket.terms.LongKeyedHashTable.rehash(LongKeyedHashTable.java:180)
```

## Корневая причина
Аналитический сервис выполнял агрегацию по полю `customer_id` (высокая кардинальность) без использования `composite aggregation` или фильтров по времени. Это привело к созданию гигантской хеш-таблицы в памяти.

## Принятые меры
1. **Circuit Breaker**: Настроен `indices.breaker.total.limit: "70%"` для предотвращения падения всей ноды.
2. **Аудит запросов**: Запрещены запросы с `size: 0` и агрегациями по нефильтрованным данным.
3. **Heap Tuning**: Heap увеличен с 8GB до 16GB.

> ⚠️ NOTE: Не забывайте, что `Xmx` не должен превышать 31GB для сохранения работы Compressed OOPs.
