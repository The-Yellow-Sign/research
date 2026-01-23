# Выбор стратегии партиционирования для Kafka-кластера

В рамках перехода на event-driven архитектуру (EDA) на языке Go, нам необходимо определить стандарт для именования и разбиения топиков на партиции.

## Текущее состояние
Сейчас используется `DefaultPartitioner`, что приводит к неравномерному распределению нагрузки при использовании пустых ключей (null keys).

## Предложенное решение
Мы будем использовать `Consistent Hashing` по `business_id` для всех событий домена `Orders`.

### Пример структуры на Go:
```go
// Message structure example
type OrderEvent struct {
    OrderID   string    `json:"order_id"` // This will be the partition key
    Status    string    `json:"status"`
    Timestamp time.Time `json:"ts"`
}
```

### Почему это важно?
1. **Ordering guarantee**: Гарантия порядка обработки событий для одного заказа.
2. **Scalability**: Возможность горизонтального масштабирования консюмер-групп.

## Таблица планируемых топиков

| Topic Name | Partitions | Retention |
| :--- | :--- | :--- |
| orders.created | 24 | 7 days |
| orders.cancelled | 12 | 7 days |
| payments.status | 32 | 14 days |

## Ссылки на стандарты
- [Internal Go Guidelines for Kafka](internal-link-to-docs)
- [Kafka Cluster Topology](architecture/kafka-topology.png)

## FIXME/TODO notes:
- FIXME: Перепроверить влияние `min.insync.replicas` на производительность в DEV-окружении.
- TODO: Описать процесс миграции существующих топиков без простоя.
