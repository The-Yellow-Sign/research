# Обновление TLS-политики для соответствия стандартам безопасности 2025

Поддержка старых версий TLS (1.0/1.1) и слабых шифров (ciphers) является серьезной угрозой безопасности. Этот документ описывает, как обновить конфигурацию Nginx.

## Рекомендуемая конфигурация
Измените файл `/etc/nginx/conf.d/ssl.conf` или соответствующий блок `server`.

```nginx
server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate /etc/letsencrypt/live/example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/example.com/privkey.pem;

    # Современные протоколы
    ssl_protocols TLSv1.2 TLSv1.3;

    # Оптимизированный набор шифров
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # HSTS (обязательно для безопасности)
    add_header Strict-Transport-Security "max-age=63072000" always;
}
```

> ⚠️ WARNING: После отключения TLS 1.1 пользователи со старыми браузерами (например, Internet Explorer 11 на Windows 7) не смогут получить доступ к сайту.

## Проверка конфигурации
После внесения изменений обязательно проверьте синтаксис и перезапустите Nginx:

```bash
nginx -t
systemctl reload nginx
```

Для глубокого аудита используйте сервис [SSL Labs](https://www.ssllabs.com/ssltest/) — ваша цель это оценка `A+`.

### Дополнительно
- См. также: [Реакция на инциденты с Nginx](nginx-emergency.md)
- [Как настроить автоматический выпуск сертификатов](nginx-tls-setup.md)
