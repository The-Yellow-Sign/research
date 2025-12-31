# Инцидент #2024-12-10: Разделение кластера Kafka (Split-Brain)

## Краткое описание
10 декабря произошел критический сбой в работе кластера Kafka в основном регионе. Из-за сетевых задержек между зонами доступности (AZ) кластер разделился на две части, что привело к потере консистентности данных в некоторых топиках.

## Хронология
- **18:00** — Рост сетевых задержек в AWS (Region: us-east-1).
- **18:05** — Zookeeper сессии брокеров начали истекать.
- **18:10** — Появление двух лидеров для одних и тех же партиций (Split-Brain).
- **18:45** — Полная деградация сервисов потребления (Consumers).
- **19:30** — Восстановление сетевой связности и ручная ресинхронизация.

## Технический анализ (Logs)

### Ошибки в логах брокера:
```text
[2024-12-10 18:06:22,442] ERROR [ReplicaFetcherThread-0-1] Error for partition [topic-a,0] to broker 1: org.apache.kafka.common.errors.NotLeaderForPartitionException
[2024-12-10 18:10:15,891] INFO [GroupCoordinator 1]: Member my-consumer-id in group my-group has failed, removing it from the group
```

### Stacktrace (Zookeeper Connection Loss):
```java
org.apache.zookeeper.KeeperException$ConnectionLossException: KeeperErrorCode = ConnectionLoss for /brokers/ids/1
    at org.apache.zookeeper.KeeperException.create(KeeperException.java:102)
    at org.apache.zookeeper.ZooKeeper.exists(ZooKeeper.java:1102)
    at kafka.zk.KafkaZkClient.checkedGetArgs(KafkaZkClient.scala:1622)
```

## Корневая причина
Параметр `zookeeper.session.timeout.ms` был установлен в слишком низкое значение (6 секунд), что при кратковременных сетевых лагах приводило к исключению брокеров из кластера и последующим бесконечным ребалансировкам.

## Принятые меры
1. **Тюнинг таймаутов**: Увеличен `zookeeper.session.timeout.ms` до 18 секунд.
2. **Мониторинг**: Добавлен алерт на разницу в `Epoch` между брокерами.
3. **Обновление**: Запланирован переход на Kafka Raft (KRaft) для исключения зависимости от Zookeeper.

> ⚠️ WARNING: В случае Split-Brain никогда не перезагружайте все ноды одновременно, иначе вы рискуете потерять те фрагменты данных, которые не успели реплицироваться.

![Схема сетевого разрыва](path/to/kafka_split_brain.png)
