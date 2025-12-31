---
title: "PostgreSQL: Connection Refused"
type: known_issue
service: postgres
---

# PostgreSQL: Connection Refused

## Ошибка

```text
psql: error: could not connect to server: Connection refused
    Is the server running on host "127.0.0.1" and accepting
    TCP/IP connections on port 5432?
could not connect to server: Connection refused
    Is the server running on host "localhost" (::1) and accepting
    TCP/IP connections on port 5432?
```

## Причина

Клиент не может установить сетевое соединение с сервером PostgreSQL. Либо сервис не запущен, либо он не слушает на указанном интерфейсе/порту, либо доступ блокируется файрволом.

## Решение

1. Проверьте статус сервиса:
   ```bash
   sudo systemctl status postgresql
   ```
2. Проверьте файл `postgresql.conf` и параметр `listen_addresses`. Он должен быть установлен в `'*'` или конкретный IP (не только `'localhost'`, если подключаетесь извне).
   ```ini
   listen_addresses = '*'
   ```
