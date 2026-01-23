---
service: node-api
title: "Документация внутреннего API сервиса уведомлений"
tags: [api, nodejs, internal]
severity: medium
---

# API микросервиса Notifications (v1)

Данный сервис отвечает за отправку Email и Push уведомлений.

## Эндпоинты

### Отправка уведомления
**POST** `/api/v1/send`

| Параметр | Тип | Описание |
| :--- | :--- | :--- |
| `user_id` | UUID | Идентификатор пользователя |
| `template` | String | Имя шаблона письма |
| `payload` | Object | Данные для вставки в шаблон |

**Пример запроса (Node.js):**
```javascript
const axios = require('axios');
axios.post('http://notif-svc/api/v1/send', {
    user_id: '550e8400-e29b-41d4-a716-446655440000',
    template: 'welcome_email'
});
```

### Статус доставки
**GET** `/api/v1/status/:message_id`

> ⚠️ NOTE: Если сервис возвращает 404, проверьте состояние Python-скрипта `mail-daemon.py`, который занимается непосредственной отправкой через SMTP. Документация этого скрипта находится в репозитории `infra-tools`.

## Ошибки
Сервис возвращает стандартные HTTP коды. 503 означает переполнение очереди RabbitMQ.
