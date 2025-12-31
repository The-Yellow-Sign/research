---
title: "Nginx: 502 Bad Gateway"
service: nginx
severity: critical
error_codes: [502, HTTP_502, upstream_error, connection_refused]
tags: [nginx, reverse-proxy, upstream, http, load-balancer]
---

# Nginx: 502 Bad Gateway

## Симптомы

Пользователи получают белую страницу с ошибкой "502 Bad Gateway" при попытке зайти на сайт или API. В браузере отображается стандартная страница ошибки Nginx. Время отклика составляет несколько секунд перед появлением ошибки. Мониторинг показывает рост числа 5xx ошибок. Некоторые запросы проходят успешно (200 OK), другие падают с 502 – проблема непостоянная. Load balancer health checks могут показывать, что бэкенды down.

## Логи и Сообщения об ошибках

```text
2025/11/28 15:12:47 [error] 18293#18293: *47821 connect() failed (111: Connection refused) while connecting to upstream, client: 203.0.113.42, server: api.example.com, request: "POST /api/v1/payments HTTP/1.1", upstream: "http://127.0.0.1:8080/api/v1/payments", host: "api.example.com", request_id: "a7f3c2e9b8d1"
2025/11/28 15:12:47 [warn] 18293#18293: *47821 upstream server temporarily disabled while connecting to upstream, client: 203.0.113.42, server: api.example.com, request: "POST /api/v1/payments HTTP/1.1", upstream: "http://127.0.0.1:8080/api/v1/payments", host: "api.example.com"
203.0.113.42 - - [28/Nov/2025:15:12:47 +0300] "POST /api/v1/payments HTTP/1.1" 502 157 "-" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" rt=0.003 uct="-" uht="-" urt="-"
```

```text
2025/11/28 15:15:33 [error] 18294#18294: *48912 upstream timed out (110: Connection timed out) while reading response header from upstream, client: 198.51.100.73, server: www.example.com, request: "GET /dashboard/analytics HTTP/1.1", upstream: "http://10.0.2.15:3000/dashboard/analytics", host: "www.example.com", referrer: "https://www.example.com/dashboard"
2025/11/28 15:15:33 [error] 18294#18294: *48912 recv() failed (104: Connection reset by peer) while reading response header from upstream, client: 198.51.100.73, server: www.example.com, request: "GET /dashboard/analytics HTTP/1.1", upstream: "http://10.0.2.16:3000/dashboard/analytics", host: "www.example.com"
198.51.100.73 - - [28/Nov/2025:15:15:33 +0300] "GET /dashboard/analytics HTTP/1.1" 502 559 "https://www.example.com/dashboard" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)" rt=60.003 uct="60.000" uht="60.000" urt="60.003"
X-Request-ID: f8c2a91d-4e3b-4f2c-9d1e-7a8c3b2e1f90
X-Upstream-Status: error
X-Upstream-Response-Time: 60.003
```

```text
2025/11/28 15:18:22 [crit] 18295#18295: *49847 open() "/var/lib/nginx/proxy/3/47/0000000473" failed (13: Permission denied) while reading upstream, client: 192.0.2.119, server: cdn.example.com, request: "GET /assets/bundle.js HTTP/1.1", upstream: "http://10.0.3.21:9000/assets/bundle.js", host: "cdn.example.com"
2025/11/28 15:18:22 [error] 18295#18295: *49847 writev() failed (32: Broken pipe) while sending request to upstream, client: 192.0.2.119, server: cdn.example.com, request: "GET /assets/bundle.js HTTP/1.1", upstream: "http://10.0.3.21:9000/assets/bundle.js", host: "cdn.example.com"
192.0.2.119 - - [28/Nov/2025:15:18:22 +0300] "GET /assets/bundle.js HTTP/1.1" 502 166 "-" "curl/7.68.0" rt=0.127 uct="0.001" uht="0.125" urt="0.001"
[error] 18295#18295: *49847 upstream prematurely closed connection while reading response header from upstream
PID: 18295
Worker: 2
Connection: 49847
Upstream: 10.0.3.21:9000
```

## Диагностика

Проверьте статус Nginx и upstream серверов:

```bash
# Проверьте, запущен ли Nginx
sudo systemctl status nginx
sudo nginx -t  # Проверка конфигурации

# Посмотрите error log в реальном времени
sudo tail -f /var/log/nginx/error.log

# Проверьте access log для паттернов
sudo tail -f /var/log/nginx/access.log | grep " 502 "
```

```bash
# Проверьте доступность upstream серверов
curl -v http://127.0.0.1:8080/health
curl -v http://10.0.2.15:3000/health

# Проверьте, что порты слушаются
sudo netstat -tlnp | grep -E ':8080|:3000|:9000'
# или
sudo ss -tlnp | grep -E ':8080|:3000'

# Проверьте connectivity
telnet 127.0.0.1 8080
nc -zv 10.0.2.15 3000
```

```bash
# Проверьте процессы backend приложений
ps aux | grep -E 'node|python|java|gunicorn|uvicorn' | grep -v grep

# Проверьте load average и ресурсы
uptime
top -bn1 | head -20
free -h

# Проверьте количество соединений к upstream
netstat -an | grep :8080 | wc -l
ss -tan | grep :3000 | grep ESTAB | wc -l
```

## Решение

**Шаг 1: Быстрая проверка upstream доступности**

```bash
# Если upstream service не запущен, запустите его
sudo systemctl status app-backend
sudo systemctl start app-backend
sudo systemctl enable app-backend

# Для PM2 (Node.js)
pm2 list
pm2 restart app-api

# Для Gunicorn (Python)
sudo systemctl restart gunicorn
# или
pkill -HUP gunicorn

# Для Java приложений
sudo systemctl restart tomcat
# или проверьте через jps
jps -l
```

**Шаг 2: Проверка и исправление Nginx конфигурации**

Проверьте upstream блок в конфигурации:

```bash
# Найдите конфигурацию upstream
grep -r "upstream" /etc/nginx/sites-enabled/
cat /etc/nginx/sites-enabled/default
```

Типичные проблемы в конфигурации:

```nginx
# Неправильно (если upstream на localhost)
upstream backend {
    server 127.0.0.1:8080;
}

# Проверьте таймауты – возможно они слишком маленькие
proxy_connect_timeout 5s;   # Слишком мало для медленных апп
proxy_read_timeout 10s;     # Увеличьте

# Правильная конфигурация с резервированием
upstream backend {
    server 10.0.2.15:8080 max_fails=3 fail_timeout=30s;
    server 10.0.2.16:8080 max_fails=3 fail_timeout=30s backup;
    keepalive 32;
}

server {
    listen 80;
    server_name api.example.com;
    
    location / {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Увеличьте таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Буферизация
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
        
        # Retry
        proxy_next_upstream error timeout http_502 http_503 http_504;
        proxy_next_upstream_tries 2;
    }
}
```

Примените изменения:

```bash
# Проверьте синтаксис
sudo nginx -t

# Перезагрузите конфигурацию без downtime
sudo nginx -s reload
# или
sudo systemctl reload nginx
```

**Шаг 3: Решение проблемы с Connection Refused**

Если upstream не слушает на нужном порту:

```bash
# Найдите, на каком порту слушает приложение
sudo lsof -i -P -n | grep LISTEN | grep -E 'node|python|java'

# Проверьте bind address (0.0.0.0 vs 127.0.0.1)
# Если приложение слушает только на 127.0.0.1, а nginx пытается подключиться по 10.x.x.x – будет ошибка

# Исправьте конфигурацию приложения чтобы слушать на 0.0.0.0
# Например для Node.js/Express:
# app.listen(8080, '0.0.0.0');

# Для Flask/Gunicorn:
gunicorn -w 4 -b 0.0.0.0:8080 app:app

# Проверьте файрвол
sudo ufw status
sudo iptables -L -n | grep 8080

# Разрешите порт если нужно
sudo ufw allow 8080/tcp
```

**Шаг 4: Решение проблемы с Timeouts**

Если upstream обрабатывает запросы слишком долго:

```bash
# Увеличьте таймауты в nginx.conf или в location блоке
sudo nano /etc/nginx/nginx.conf
```

Добавьте в http блок или location:

```nginx
proxy_connect_timeout 300s;
proxy_send_timeout 300s;
proxy_read_timeout 300s;
send_timeout 300s;
```

Оптимизируйте backend приложение:

```bash
# Проверьте slow queries (для DB-heavy приложений)
# PostgreSQL:
psql -c "SELECT pid, state, query_start, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start LIMIT 10;"

# MySQL:
mysql -e "SHOW FULL PROCESSLIST;"

# Добавьте индексы, оптимизируйте запросы
# Масштабируйте horizontally – добавьте больше upstream серверов
```

**Шаг 5: Исправление прав доступа на proxy cache**

Если ошибка связана с правами:

```bash
# Проверьте владельца директорий
ls -la /var/lib/nginx/
ls -la /var/lib/nginx/proxy/

# Исправьте права
sudo chown -R www-data:www-data /var/lib/nginx/proxy/
sudo chmod -R 755 /var/lib/nginx/proxy/

# Или очистите cache
sudo rm -rf /var/lib/nginx/proxy/*
sudo systemctl restart nginx
```

**Шаг 6: Мониторинг и алертинг**

```bash
# Настройте мониторинг upstream в nginx
# Используйте nginx-module-vts или commercial nginx plus

# Добавьте healthcheck скрипт
cat > /usr/local/bin/nginx_upstream_check.sh <<'EOF'
#!/bin/bash
STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/health)
if [ "$STATUS" != "200" ]; then
    echo "Upstream is down! Status: $STATUS"
    systemctl restart app-backend
    curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK \
         -d '{"text":"Upstream backend restarted due to health check failure"}'
fi
EOF

chmod +x /usr/local/bin/nginx_upstream_check.sh
echo "*/2 * * * * /usr/local/bin/nginx_upstream_check.sh" | crontab -

# Настройте Prometheus nginx-exporter
# https://github.com/nginxinc/nginx-prometheus-exporter
```

**Шаг 7: Постоянное решение**

- Используйте connection pooling и keepalive
- Настройте graceful shutdown для backend приложений
- Добавьте health check endpoints
- Используйте load balancing с несколькими upstream серверами
- Включите circuit breaker pattern на уровне приложения
- Настройте auto-scaling для backend (k8s HPA, AWS ASG)
