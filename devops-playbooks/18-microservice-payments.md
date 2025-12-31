---
title: "Микросервис платежей"
---

# Микросервис платежей

Этот микросервис обрабатывает финансовые транзакции между аккаунтами. Реализован на **Java Spring Boot** и использует **Kafka** для асинхронного обмена событиями. Основные шаги:
1. Приём POST‑запроса `/pay` с полями `from_account`, `to_account`, `amount`.
2. Проверка баланса отправителя в базе **PostgreSQL**.
3. Создание записи о транзакции и публикация события `payment.initiated` в Kafka.
4. Сервис **PaymentProcessor** потребляет событие, списывает средства и публикует `payment.completed`.
5. При ошибке – публикует `payment.failed` и откатывает транзакцию.

### Особенности
- **Idempotency** через `transaction_id` – повторные запросы безопасны.
- **Транзакционная согласованность** с помощью `@Transactional`.
- **Мониторинг**: метрики `payment_success_total`, `payment_failure_total` экспортируются через **Micrometer** в Prometheus.

### Пример запроса
```bash
curl -X POST https://pay.example.com/pay \
  -H "Content-Type: application/json" \
  -d '{"from_account":"123","to_account":"456","amount":99.95,"transaction_id":"tx-20251128-001"}'
```
Токен доступа передаётся в заголовке `Authorization: Bearer <jwt>`.
