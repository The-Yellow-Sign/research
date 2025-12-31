---
service: redis
title: "Проблемы с переключением ролей в Redis Sentinel"
tags: [redis, sentinel, high-availability]
---

# Устранение сбоев Failover в Redis Sentinel

## Описание проблемы
При падении мастера Redis, Sentinel не инициирует автоматическое переключение на слейв (promotion). В логах Sentinel видны сообщения о невозможности достичь кворума или ошибки аутентификации.

## Диагностика

### 1. Проверка состояния Sentinel
Используйте "грязный" способ через старый `redis-cli` (deprecated, но часто встречается в скриптах):

```bash
# TODO: Переписать на использование redis-cli --sentinel в новых образах
redis-cli -p 26379 sentinel masters
```

### 2. Анализ логов Sentinel
Ищите ключевые слова `+sdown` (subjectively down) и `+odown` (objectively down).

```text
2024-12-25 10:00:01.123 # +sdown master mymaster 127.0.0.1 6379
2024-12-25 10:00:11.456 # +odown master mymaster 127.0.0.1 6379 #quorum 2/2
2024-12-25 10:00:11.456 # +new-epoch 1
```

## Типичные причины

- **Нехватка кворума**: Убедитесь, что запущены как минимум 3 инстанса Sentinel.
- **Пароли**: Redis Sentinel требует настройки `sentinel auth-pass <master-name> <password>`, если мастер защищен паролем.
- **Networking**: Проверьте, что Sentinel может подключиться к IP, который мастер анонсирует как `announced-ip`.

## Исправление
Если Sentinel "потерял" конфигурацию, можно попробовать сбросить состояние:

```bash
redis-cli -p 26379 sentinel reset mymaster
```

> [!WARNING]
> Ручное переключение через `sentinel failover` может привести к потере данных, если слейв сильно отстает от мастера.
