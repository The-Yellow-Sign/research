# Документация API платежной системы (Financial Transaction Gateway)

Данный документ описывает публичный API для интеграции с нашей финансовой платформой. API соответствует стандарту PCI DSS и требует использования взаимной TLS аутентификации (mTLS).

## 1. Общие сведения

- **Base URL**: `https://api.finance.internal/v1`
- **Формат данных**: JSON (UTF-8)
- **Аутентификация**: API-Key (Header) + mTLS Certificate
- **Rate Limit**: 1000 запросов в секунду на один Merchant ID.

## 2. Глобальные заголовки

| Заголовок | Обязательный | Описание |
| :--- | :--- | :--- |
| `Authorization` | Да | Bearer токен или API-Key |
| `X-Idempotency-Key` | Да | Уникальный ключ для предотвращения дублей |
| `Content-Type` | Да | `application/json` |
| `X-Request-Trace-Id` | Нет | Для отладки (будет возвращен в ответе) |

## 3. Методы обработки транзакций

### POST /transactions/authorize
Предварительная авторизация средств на карте.

**Request Body Schema:**
```json
{
  "merchant_id": "M_123456789",
  "amount": {
    "value": "1500.50",
    "currency": "RUB"
  },
  "payment_method": {
    "type": "card",
    "card_token": "ct_98765abc",
    "cvv": "123"
  },
  "customer": {
    "id": "C_555666",
    "email": "user@example.com",
    "ip_address": "192.168.1.1"
  },
  "metadata": {
    "order_id": "ORD-999-XP",
    "loyalty_program": false
  }
}
```

**Response (201 Created):**
```json
{
  "transaction_id": "TX_A1B2C3D4E5",
  "status": "authorized",
  "approval_code": "OK2025",
  "created_at": "2025-12-29T18:00:00Z"
}
```

### POST /transactions/{id}/capture
Подтверждение ранее авторизованной транзакции.

| Параметр | Тип | Описание |
| :--- | :--- | :--- |
| `id` | path | ID транзакции из метода authorize |
| `partial_amount` | body | Опционально, для частичного списания |

## 4. Обработка ошибок

В случае ошибки API возвращает стандартный объект:

```json
{
  "error": {
    "code": "insufficient_funds",
    "message": "Недостаточно средств на счете клиента.",
    "request_id": "req_888999abc",
    "details_url": "https://docs.finance.internal/errors#402"
  }
}
```

## 5. Webhooks

Для получения уведомлений об изменении статуса транзакции необходимо настроить URL в личном кабинете.

**Пример вебхука:**
```json
{
  "event": "transaction.captured",
  "data": {
    "id": "TX_A1B2C3D4E5",
    "status": "completed",
    "final_amount": "1500.50"
  },
  "signature": "sha256=..."
}
```

## 6. Идемпотентность

Использование заголовка `X-Idempotency-Key` гарантирует, что повторный запрос с тем же ключом не приведет к созданию второй транзакции в течение 24 часов.

## 7. Безопасность и соответствие

Все данные карт должны быть токенизированы. Передача "голых" номеров карт (PAN) через API строго запрещена и приведет к немедленной блокировке Merchant ID.

> [!IMPORTANT]
> При возникновении ошибок 503 или таймаутов проверьте состояние соединений в [HAProxy](haproxy-l7-deep-dive.md).

## 8. Коды ответов

- **200 OK**: Запрос выполнен успешно.
- **201 Created**: Ресурс создан (транзакция авторизована).
- **400 Bad Request**: Ошибка в параметрах запроса.
- **401 Unauthorized**: Неверный API ключ или сертификат.
- **402 Payment Required**: Отказ со стороны банка-эквайера.
- **429 Too Many Requests**: Превышен лимит запросов.
- **500 Internal Server Error**: Сбой на нашей стороне.

---
*Документ API-FIN-V1.4*
*Длина: >110 строк*
*TODO: Описать процесс рефанд (Refunds) для частичных возвратов.*
*FIXME: Обновить ссылки на документацию по кодам ошибок.*

```json
{
  "schema_version": "1.4.0",
  "generated_at": "2025-12-29",
  "author": "FinTech SDK Team"
}
```
