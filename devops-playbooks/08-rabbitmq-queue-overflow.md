---
title: "RabbitMQ: Queue Overflow"
service: rabbitmq
severity: warning
error_codes: [queue_overflow, max_length_exceeded, 406]
tags: [rabbitmq, queue, messaging, overflow, broker]
---

# RabbitMQ: Queue Overflow

## Симптомы

Сообщения не попадают в очередь RabbitMQ, publisher получает reject. Queue достигла максимальной длины. Мониторинг показывает миллионы сообщений в очереди. Consumer не успевает обрабатывать messages. Memory warning в RabbitMQ management UI. Приложение теряет события.

## Логи и Сообщения об ошибок

```text
2025-11-28 17:05:42 [warning] <0.18293.42> Queue 'tasks.processing' in vhost '/' has reached max-length limit of 1000000
2025-11-28 17:05:42 [error] <0.18294.42> Channel error on connection <0.18291.42> (10.0.2.47:52183 -> 10.0.1.10:5672): operation queue.declare caused a channel exception precondition_failed: 406
Node: rabbit@rabbitmq-1
Queue: tasks.processing
Messages: 1000000
Max length: 1000000
Memory used: 4.2GB
Consumer count: 5
```

```text
[2025-11-28T17:08:19.284] ERROR AMQPChannelError: (406, "PRECONDITION_FAILED - queue max-length exceeded")
pika.exceptions.AMQPChannelError: (406, "PRECONDITION_FAILED")
  File "/app/messaging/publisher.py", line 67, in publish_message
    channel.basic_publish(exchange='tasks', routing_key='processing', body=message)
Queue: tasks.processing
Messages ready: 1000000
Unacked messages: 847
Consumer utilization: 23%
Message rate (in): 5000/s
Message rate (out): 350/s
Request ID: f8c2a91d-4e3b-4f2c-9d1e
```

```text
java.io.IOException: com.rabbitmq.client.ShutdownSignalException: channel error; protocol method: #method<channel.close>(reply-code=406, reply-text=PRECONDITION_FAILED - max-length, class-id=50, method-id=10)
	at com.rabbitmq.client.impl.AMQChannel.wrap(AMQChannel.java:129)
	at com.rabbitmq.client.impl.ChannelN.basicPublish(ChannelN.java:619)
	at com.company.messaging.TaskPublisher.send(TaskPublisher.java:94)
Queue overflow policy: reject-publish
Queue name: tasks.processing
Max length: 1000000
Messages in queue: 1000000
Thread: publisher-thread-8
```

## Диагностика

```bash
# Проверьте очереди
rabbitmqctl list_queues name messages consumers message_bytes

# Детальная информация
rabbitmqctl list_queues name messages_ready messages_unacknowledged \
  memory consumer_utilisation

# Через API
curl -u guest:guest http://localhost:15672/api/queues
```

## Решение

**Шаг 1:** Увеличьте consumer capacity

```bash
# Добавьте больше consumers
# В коде приложения увеличьте workers

# Масштабируйте consumer pods (k8s)
kubectl scale deployment task-consumer --replicas=10
```

**Шаг 2:** Настройте overflow policy

```bash
rabbitmqctl set_policy tasks-overflow \
  "tasks.*" \
  '{"max-length":1000000,"overflow":"drop-head"}' \
  --apply-to queues

# drop-head - удалять старые
# reject-publish - отклонять новые
```

**Шаг 3:** Purge если критично

```bash
rabbitmqctl purge_queue tasks.processing
```
