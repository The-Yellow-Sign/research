---
title: "Nginx: 413 Request Entity Too Large"
type: known_issue
service: nginx
---

# Nginx: 413 Request Entity Too Large

## Ошибка

```text
<html>
<head><title>413 Request Entity Too Large</title></head>
<body>
<center><h1>413 Request Entity Too Large</h1></center>
<hr><center>nginx/1.18.0 (Ubuntu)</center>
</body>
</html>
```

В логах (`/var/log/nginx/error.log`):
```text
2025/11/28 15:22:11 [error] 1234#1234: *56 client intended to send too large body: 15728640 bytes, client: 192.168.1.5, server: example.com, request: "POST /upload HTTP/1.1", host: "example.com"
```

## Причина

Клиент пытается загрузить файл, размер которого превышает лимит, установленный в конфигурации Nginx (по умолчанию 1MB).

## Решение

Увеличьте параметр `client_max_body_size` в блоке `http`, `server` или `location` конфигурации Nginx.

```nginx
http {
    client_max_body_size 100M;
    ...
}
```
*После изменения перезагрузите Nginx: `sudo nginx -s reload`.*
