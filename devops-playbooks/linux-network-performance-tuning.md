# Тюнинг сетевого стека Linux для высоконагруженных систем (10GbE+)

Когда сервер обрабатывает десятки и сотни тысяч запросов в секунду, стандартные настройки ядра (kernel) становятся "бутылочным горлышком". Это руководство описывает низкоуровневые настройки сетевого стека для минимизации задержек и исключения потерь пакетов.

## 1. Лимиты очередей и буферов

При высокой нагрузке очереди сетевой карты или ядра могут переполниться.

### Сетевая карта (Ring Buffers)
Увеличьте размер кольцевых буферов для обработки всплесков трафика.
```bash
# Просмотр текущих значений
ethtool -g eth0

# Установка максимальных значений
ethtool -G eth0 rx 4096 tx 4096
```

### Ядро (Backlog)
Параметр `net.core.netdev_max_backlog` определяет размер очереди пакетов, ожидающих обработки ядром.

```bash
sysctl -w net.core.netdev_max_backlog=65536
```

## 2. Тюнинг TCP стека

### Буферы TCP соединений
Увеличьте максимальный объем памяти для TCP буферов (read/write).

```bash
# Min, Default, Max (в байтах)
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```

### Обработка TIME_WAIT
Для систем с миллионами коротких соединений (например, балансировщики) важно быстро переиспользовать порты.

```bash
net.ipv4.tcp_tw_reuse = 1
net.ipv4.ip_local_port_range = 1024 65535
net.ipv4.tcp_max_tw_buckets = 262144
```

## 3. Interrupt Coalescing и RSS

### Interrupt Moderation
Слишком частые прерывания CPU от сетевой карты могут привести к высокому `system cpu load`.
```bash
# Адаптивное управление прерываниями
ethtool -C eth0 adaptive-rx on adaptive-tx on
```

### Receive Side Scaling (RSS)
Убедитесь, что прерывания распределяются по всем ядрам CPU, а не только по первому.
```bash
cat /proc/interrupts | grep eth0
# Используйте irqbalance или настройте /proc/irq/*/smp_affinity вручную
```

## 4. Контроль перегрузки (Congestion Control)

Для современных сетей с низкой потерей пакетов и высокой пропускной способностью алгоритм **BBR** от Google работает лучше стандартного CUBIC.

```bash
# Проверка доступных алгоритмов
sysctl net.ipv4.tcp_available_congestion_control

# Включение BBR
sysctl -w net.core.default_qdisc=fq
sysctl -w net.ipv4.tcp_congestion_control=bbr
```

## 5. Мониторинг сетевых ошибок

Используйте `netstat -s` или `nstat` для поиска проблем:

- `TcpExtListenOverflows`: Очередь `accept()` переполнена (увеличьте `somaxconn`).
- `TcpExtListenDrops`: Ядро отбросило пакеты из-за нехватки ресурсов.
- `TcpRetransSegs`: Процент ретрансмиссий (в норме < 1%).

## 6. Резюме настроек (/etc/sysctl.conf)

```text
# --- NETWORK TUNING ---
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65536
net.ipv4.tcp_max_syn_backlog = 16384
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_fin_timeout = 15
net.ipv4.tcp_keepalive_time = 300
net.ipv4.tcp_max_orphans = 262144
net.ipv4.tcp_syn_retries = 2
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_fastopen = 3

# TCP Buffers
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# BBR
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
```

## 7. Применение без перезагрузки
```bash
sysctl -p
```

> [!TIP]
> Настройки `sysctl` действуют глобально. Если на сервере запущены контейнеры, некоторые параметры (например, из неймспейса `net.ipv4.*`) могут быть переопределены внутри контейнера, если используется `network mode: bridge`.

## Ссылки
- [Тюнинг HAProxy](haproxy-l7-deep-dive.md)
- [Инцидент с Split-Brain в Kafka](kafka-incident-december.md)
- [Оптимизация Nginx](nginx-tuning-compression.md)

---
*Документ PERF-NET-2025*
*Линий в файле: >115*
*TODO: Описать настройку Hugepages для баз данных.*
