---
title: "Apache: High CPU Usage"
service: apache
severity: warning
error_codes: [high_cpu, worker_saturation, prefork_maxed]
tags: [apache, httpd, cpu, performance, web-server]
---

# Apache: High CPU Usage

## Симптомы

Apache процесс потребляет 90-100% CPU. Веб-сайт работает медленно, время отклика увеличено. Load average сервера высокий (>5). Новые запросы ставятся в очередь. Мониторинг показывает MaxRequestWorkers достигнут. Пользователи получают timeout errors.

## Логи и Сообщения об ошибках

```text
[Thu Nov 28 17:25:42.392847 2025] [mpm_prefork:error] [pid 18293] AH00161: server reached MaxRequestWorkers setting, consider raising the MaxRequestWorkers setting
[Thu Nov 28 17:25:42.718294 2025] [mpm_prefork:warn] [pid 18293] AH00167: long lost child came home! (pid 18472)
[Thu Nov 28 17:25:43.192847 2025] [core:error] [pid 18591] (12)Cannot allocate memory: fork: Unable to fork new process
Apache/2.4.52 (Ubuntu)
Server load: 8.47 5.92 4.18
Processes: 256/256 (MaxRequestWorkers)
CPU usage: 98.4%
Memory: 7.2GB / 8GB
Active connections: 847
```

```text
top - 17:27:19 up 15 days,  3:42,  2 users,  load average: 8.47, 5.92, 4.18
Tasks: 412 total,  89 running, 323 sleeping
%Cpu(s): 94.2 us,  3.8 sy,  0.0 ni,  0.0 id,  1.2 wa,  0.0 hi,  0.8 si
PID    USER     PR  NI    VIRT    RES  %CPU  %MEM     TIME+ COMMAND
18293  www-data 20   0  524288 184320  12.3   2.3   0:47.28 apache2
18294  www-data 20   0  524288 184320  12.1   2.3   0:46.94 apache2
18295  www-data 20   0  524288 184320  11.9   2.3   0:47.12 apache2
[repeated 256 times]
Total Apache CPU: 3084% (of 3200% available on 32-core)
```

```text
[2025-11-28 17:28:47] ERROR mod_php: script execution timeout
PHP Fatal error: Maximum execution time of 30 seconds exceeded in /var/www/html/process.php on line 147
[Thu Nov 28 17:28:47.847291 2025] [php7:error] [pid 18847] [client 203.0.113.42:52183] script '/var/www/html/process.php' exceeded execution time limit
Request: POST /process.php
Client: 203.0.113.42
Execution time: 30.842 seconds
Memory: 128MB
Query: SELECT * FROM users WHERE status='active'  -- 8.4M rows, no index
Apache worker: process 18847
Thread: N/A (prefork MPM)
```

## Диагностика

```bash
# Проверьте процессы Apache
ps aux | grep apache2 | wc -l
top -u www-data

# Проверьте статус
apacheci -S
apache2ctl status

# Проверьте active connections
netstat -an | grep :80 | wc -l
ss -tan | grep :80 | grep ESTAB | wc -l

# Найдите медленные запросы (если mod_status включен)
curl http://localhost/server-status
```

## Решение

**Шаг 1:** Увеличьте workers

```bash
sudo nano /etc/apache2/mods-available/mpm_prefork.conf

# Измените:
<IfModule mpm_prefork_module>
    StartServers             10
    MinSpareServers          10
    MaxSpareServers          20
    MaxRequestWorkers        400
    MaxConnectionsPerChild   1000
</IfModule>

sudo systemctl restart apache2
```

**Шаг 2:** Переключитесь на event MPM

```bash
sudo a2dismod mpm_prefork
sudo a2dismod php7.4
sudo a2enmod mpm_event
sudo a2enmod proxy_fcgi setenvif
sudo a2enconf php7.4-fpm

sudo systemctl restart apache2
sudo systemctl start php7.4-fpm
```

**Шаг 3:** Оптимизируйте PHP

```bash
sudo nano /etc/php/7.4/fpm/pool.d/www.conf

# Увеличьте workers
pm = dynamic
pm.max_children = 50
pm.start_servers = 10
pm.min_spare_servers = 5
pm.max_spare_servers = 15

sudo systemctl restart php7.4-fpm
```
