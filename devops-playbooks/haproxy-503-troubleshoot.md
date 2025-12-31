## Ошибки 503 и задержки в HAProxy при высокой нагрузке

Данный документ описывает решение проблем с исчерпанием ресурсов на уровне ядра Linux и конфигурации HAProxy.

### Симптомы
В логах HAProxy наблюдается большое количество сообщений `sC--` (server connection failure) или `sD--` (server session termination). Пользователи жалуются на периодические ошибки 503 Service Unavailable.

### Диагностика
Проверьте количество открытых соединений и лимиты системы.

```bash
# Просмотр текущих соединений (УСТАРЕВШИЙ СПОСОБ)
# TODO: Перейти на использование ss вместо netstat
netstat -an | grep :80 | wc -l
```

Проверьте логи ядра на наличие ошибок переполнения очереди:
```bash
dmesg | grep "TCP: request_sock_TCP: Possible SYN flooding on port"
```

### Решение

#### 1. Тюнинг параметров ядра (Sysctl)
Для работы с большим количеством одновременных соединений необходимо увеличить лимиты в `/etc/sysctl.conf`.

```text
# ПРЕДУПРЕЖДЕНИЕ: Параметр net.ipv4.tcp_tw_recycle УСТАРЕЛ и удален в ядрах 4.12+
# net.ipv4.tcp_tw_recycle = 1  <-- НЕ ИСПОЛЬЗОВАТЬ

net.ipv4.ip_local_port_range = 1024 65000
net.ipv4.tcp_tw_reuse = 1
net.core.somaxconn = 65535
```

#### 2. Конфигурация HAProxy
Увеличьте значение `maxconn` в глобальной секции и в секции defaults.

```haproxy
global
    maxconn 100000

defaults
    maxconn 100000
    timeout connect 5s
    timeout client 50s
    timeout server 50s
```

> [!NOTE]
> Убедитесь, что лимиты `ulimit -n` для пользователя haproxy позволяют открывать нужное количество файлов.

Смотрите также: [Оптимизация Nginx](nginx-tuning-compression.md)
