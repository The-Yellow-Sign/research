---
title: Фикс 502 Bad Gateway на Nginx
---

# Быстрые заметки по troubleshooting Nginx

Если вы видите 502 Bad Gateway, скорее всего ваш upstream сервис "лежит" или не успевает отвечать.

## Check active connections
Run this to see what's happening on the machine:
```bash
netstat -tulpn | grep :80
```

## Logs investigation
Check the error log for `upstream prematurely closed connection`:
```bash
tail -f /var/log/nginx/error.log | grep upstream
```

## Potential solutions
1. **Service status**: Check if your backend (Node.js/Go/Python) is running.
   `systemctl status target-service`
2. **Proxy timeout**: Sometimes you need to increase timeouts in `nginx.conf`:
   ```nginx
   proxy_read_timeout 300;
   proxy_connect_timeout 300;
   proxy_send_timeout 300;
   ```

> ⚠️ WARNING: Не ставьте таймауты выше 60 секунд для публичных API без веской причины.

TODO: Добавить описание для PHP-FPM сокетов.
![Diagram showing hop flow](path/to/nginx_flow.png)
