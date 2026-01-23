---
title: "Инцидент #2024-11-28: Потеря связи с Azure Database for MySQL"
service: azure
---

# Post-mortem: Прерывание соединений с БД в регионе West Europe

## Краткое описание
28 ноября 2024 года в течение 45 минут наблюдалась нестабильность сетевого соединения между кластером AKS и инстансом Azure Database for MySQL (Flexible Server). Около 30% запросов завершались ошибкой `Connection reset by peer`.

## Хронология
- **10:15** — Рост ошибок в сервисе `auth-service`.
- **10:20** — Мониторинг Azure показал падение сетевой связности в зоне Availability Zone 1.
- **10:35** — Попытка автоматического переключения на Secondary Instance (Failover) не удалась из-за проблем с DNS в Azure.
- **11:00** — Сеть стабилизировалась силами дата-центра Microsoft.

## Технический анализ (Logs)

### Логи из приложения (Java):
```text
com.mysql.cj.jdbc.exceptions.CommunicationsException: Communications link failure
The last packet successfully received from the server was 1,000 milliseconds ago.
    at com.mysql.cj.jdbc.exceptions.SQLError.createCommunicationsException(SQLError.java:174)
    at com.mysql.cj.protocol.a.NativeProtocol.readMessage(NativeProtocol.java:555)
...
Caused by: java.net.SocketException: Connection reset
```

### Логи из Azure Resource Health:
```json
{
  "timestamp": "2024-11-28T10:20:00Z",
  "status": "Degraded",
  "reason": "Intermittent network latency and packet loss observed in West Europe."
}
```

## Корневая причина
Внутренний сбой в SDN (Software Defined Network) облака Azure в конкретном регионе. Прямого влияния со стороны наших конфигураций не выявлено, однако процесс Failover в Azure Flexible Server оказался медленнее ожидаемого.

## Принятые меры
- **Retry Logic**: Внедрен экспоненциальный откат (exponential backoff) для всех критических соединений с БД.
- **Multi-region**: Начато исследование возможности развертывания Read Replica в другом регионе (North Europe).
- **Timeouts**: Значение `connectTimeout` в JDBC строке уменьшено до 5 секунд для более быстрого обнаружения сбоев.

> [!NOTE]
> Данный инцидент подчеркивает важность наличия локального кеша (например, Redis) для критических данных профиля пользователя.
