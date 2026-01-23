---
service: haproxy
title: "Глубокая отладка L7 маршрутизации и липких сессий в HAProxy"
tags: [haproxy, troubleshooting, l7, sticky-sessions]
---

# Устранение сложных проблем маршрутизации на уровне L7 в HAProxy

Этот документ представляет собой исчерпывающее руководство по диагностике и решению проблем с распределением трафика на основе путей (path-based routing) и механизмов сохранения сессий (sticky sessions).

## 1. Проблемы с маршрутизацией по путям (ACL)

Иногда запросы уходят не в тот backend, хотя правила в конфигурации кажутся верными. Это часто связано с порядком обработки ACL или нечеткими регулярными выражениями.

### Сценарий: Конфликт префиксов
Если у вас есть `/api` и `/api/v2`, HAProxy может выбрать первое правило, если оно стоит выше.

```haproxy
frontend main-https
    bind *:443 ssl crt /etc/ssl/certs/
    
    # ПЛОХО: Запрос к /api/v2/users попадет в backend-v1
    use_backend backend-v1 if { path_beg /api }
    use_backend backend-v2 if { path_beg /api/v2 }
```

**Решение**: Всегда располагайте более специфичные правила выше или используйте точное соответствие.

```haproxy
    # ХОРОШО: Проверка самого длинного пути в первую очередь
    use_backend backend-v2 if { path_beg /api/v2 }
    use_backend backend-v1 if { path_beg /api }
```

### Диагностика через логи
Включите расширенное логирование HTTP запросов, чтобы видеть, какой ACL сработал.

```haproxy
    log-format "%ci:%cp [%tr] %ft %b/%s %TR/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"
```

## 2. Сбои механизмов Sticky Sessions

"Липкие сессии" необходимы для legacy-приложений, которые хранят состояние (state) в памяти сервера. Если сессия "прыгает", пользователь будет постоянно разлогиниваться.

### Метод 1: Вставка Cookie (Cookie Insertion)
Это самый надежный способ. HAProxy сам добавляет cookie в ответ.

```haproxy
backend app-servers
    balance roundrobin
    cookie SRVNAME insert indirect nocache
    server s1 10.0.0.1:80 check cookie s1
    server s2 10.0.0.2:80 check cookie s2
```

**Типичные ошибки**:
- **nocache**: Если этого флага нет, промежуточные прокси могут закешировать cookie сессии.
- **indirect**: Позволяет не отправлять cookie, если у клиента она уже есть.

### Метод 2: Таблицы соответствия (Stick Tables)
Используются, когда нельзя менять заголовки ответа.

```haproxy
backend dynamic-backend
    stick-table type ip size 1m expire 30m
    stick on src
    server s1 10.0.0.1:80 check
```

> [!WARNING]
> Stick-таблицы хранятся в памяти одного процесса. При перезагрузке HAProxy все привязки будут сброшены, если не настроена репликация через `peers`.

## 3. Отладка через CLI (Runtime API)

HAProxy предоставляет мощный инструмент для просмотра состояния в реальном времени.

```bash
# Просмотр всех сессий на конкретном бекенде
echo "show sess" | socat stdio /var/run/haproxy.sock

# Изменение веса сервера без рестарта
echo "set server backend-app/s1 weight 50%" | socat stdio /var/run/haproxy.sock

# Просмотр содержимого stick-таблицы
echo "show table dynamic-backend" | socat stdio /var/run/haproxy.sock
```

## 4. Чек-лист при возникновении 502/503

1. **Check Timeout**: Проверьте, не слишком ли агрессивны проверки здоровья (health checks).
   - `inter 2s fall 3 rise 2` — это 6 секунд до признания сервера "падшим".
2. **MaxConn**: Проверьте, не упираетесь ли вы в лимиты `maxconn` в секции `global`.
3. **Internal Errors**: Ищите в логах флаги завершения сессии.
   - `sH--`: Сервер закрыл соединение до обработки заголовков.
   - `cH--`: Тайм-аут клиента.

## 5. Дополнительная настройка ядра Linux
Для HAProxy крайне важны параметры сетевого стека.

```bash
# Увеличение очереди входящих соединений
sysctl -w net.core.somaxconn=65535
# Увеличение диапазона портов для коннекта к бекендам
sysctl -w net.ipv4.ip_local_port_range="1024 65000"
```

![Схема распределения трафика](path/to/haproxy_l7_flow.png)

## Ссылки для изучения
- [HAProxy Configuration Manual](http://cbonte.github.io/haproxy-dconv/2.8/configuration.html)
- [Статья по тюнингу TCP стека](haproxy-503-troubleshoot.md)
- [Мониторинг через тики в Grafana](k8s-monitoring-setup.md)

---
*Документ подготовлен командой SRE, 2025*
*TODO: Добавить описание Lua-скриптов для кастомной логики.*
