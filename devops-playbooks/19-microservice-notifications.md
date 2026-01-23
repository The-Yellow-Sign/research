---
title: "Микросервис уведомлений"
---

# Микросервис уведомлений

Сервис отвечает за отправку email‑ и push‑уведомлений пользователям. Реализован на **Python FastAPI** и использует **Redis** как очередь задач (RQ). При получении POST‑запроса `/notify` с параметрами `user_id`, `type` и `payload` сервис:
1. Формирует сообщение в зависимости от `type` (email, sms, push).
2. Помещает задачу в очередь Redis (`notifications` queue).
3. Рабочий процесс (worker) берёт задачу, отправляет сообщение через внешние провайдеры (SendGrid, Twilio, Firebase).
4. Статус доставки записывается в PostgreSQL для аудита.

### Ключевые свойства
- **Retry‑logic** с экспоненциальным бэкофом через RQ‑retry.
- **Rate limiting** на уровне провайдера (10 запросов/сек).
- **Метрики** `notifications_sent_total` и `notifications_failed_total` экспортируются в Prometheus.

### Пример вызова
```bash
curl -X POST https://notify.example.com/notify \
  -H "Content-Type: application/json" \
  -d '{"user_id": "42", "type": "email", "payload": {"subject": "Welcome", "body": "Hello!"}}'
```
