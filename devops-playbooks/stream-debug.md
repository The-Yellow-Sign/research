---
service: kafka
title: "Устранение задержек (lag) в Consumer Group при работе в Docker"
tags: [kafka, docker, troubleshooting, performance]
severity: high
---

# Диагностика и решение проблем с Kafka Consumer Lag

## Описание проблемы
Наблюдается резкое увеличение lag в определенных consumer groups. Данные в топики поступают с нормальной скоростью, однако консьюмеры, запущенные в Docker-контейнерах, не успевают их обрабатывать. Это приводит к задержкам в бизнес-логике и переполнению дискового пространства из-за retention policy.

## Шаги по диагностике

### 1. Проверка текущего состояния lag
Для начала необходимо определить, на каких именно партициях происходит задержка.

```bash
docker exec -it kafka-broker kafka-consumer-groups --bootstrap-server localhost:9092 --describe --group my-consumer-group
```

### 2. Анализ ресурсов контейнера
Часто причиной является throttling CPU или нехватка памяти, из-за чего JVM Garbage Collector начинает работать слишком агрессивно.

```bash
docker stats my-consumer-container
```

> ⚠️ WARNING: Если CPU Usage приближается к лимиту, установленному в docker-compose или k8s, Kafka Consumer может пропускать heartbeats, что приведет к постоянным ребалансировкам (rebalancing).

### 3. Проверка сетевых задержек
Поскольку Kafka работает внутри Docker, проверьте настройки `KAFKA_ADVERTISED_LISTENERS`. Неправильная конфигурация может привести к тому, что клиент будет пытаться подключиться к внутреннему IP контейнера, который недоступен снаружи.

## Варианты решения

### Увеличение параллелизма
Если одна партиция обрабатывается слишком медленно, убедитесь, что количество консьюмеров в группе соответствует количеству партиций в топике.

### Оптимизация параметров JVM
Добавьте следующие переменные окружения в ваш Docker-контейнер для оптимизации работы памяти:

```yaml
services:
  consumer:
    image: my-kafka-consumer:latest
    environment:
      - JAVA_TOOL_OPTIONS="-Xms2g -Xmx2g -XX:+UseG1GC"
      - KAFKA_FETCH_MIN_BYTES=1024
      - KAFKA_FETCH_MAX_WAIT_MS=500
```

### Логирование
Проверьте логи на наличие ошибок аутентификации или таймаутов:

```text
[2025-12-29 14:22:01,442] INFO [Consumer clientId=consumer-1, groupId=my-group] Group coordinator lookup failed: The coordinator is not available. (org.apache.kafka.clients.consumer.internals.AbstractCoordinator)
[2025-12-29 14:22:05,891] ERROR [Consumer clientId=consumer-1, groupId=my-group] Offset commit failed on partition my-topic-0 at offset 12345: The request timed out. (org.apache.kafka.clients.consumer.internals.ConsumerCoordinator)
```

## Дополнительные материалы
- [Настройка мониторинга Kafka через Prometheus](prometheus-setup-guide.md)
- [Официальная документация Kafka](https://kafka.apache.org/documentation/)

![Схема потока данных](path/to/kafka_flow.png)

### Полезные ссылки
- [Kafka-UI для визуализации](https://github.com/provectus/kafka-ui)
- [Статья по тюнингу производительности Kafka](https://strimzi.io/blog/)

---
*Документ обновлен 2025-12-29*
