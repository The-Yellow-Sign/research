---
title: "Настройка TLS в Nginx"
type: guide
service: nginx
---

# Настройка TLS в Nginx

## Введение

TLS (HTTPS) защищает передаваемые данные от перехвата и подмены. В продакшн‑окружении важно правильно сконфигурировать сертификаты, протоколы и параметры шифрования, чтобы обеспечить высокий уровень безопасности и совместимость с клиентами.

## Требования

- ОС: Linux (Ubuntu 20.04+, CentOS 8+)
- Nginx 1.18+ (с поддержкой `http_ssl_module`)
- Доступ к сертификатам в формате PEM (fullchain и private key)
- Пакет `openssl` установлен для генерации самоподписанных сертификатов (для тестов)

## Пошаговая инструкция

### Шаг 1: Получите сертификат

#### 1.1 Самоподписанный (только для тестов)

```bash
openssl req -newkey rsa:4096 -nodes -keyout /etc/nginx/ssl/nginx.key \
  -x509 -days 365 -out /etc/nginx/ssl/nginx.crt \
  -subj "/C=RU/ST=Moscow/L=Moscow/O=Example Corp/OU=IT/CN=example.com"
```

#### 1.2 Let's Encrypt (production)

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d example.com -d www.example.com
```

### Шаг 2: Создайте директорию для сертификатов

```bash
sudo mkdir -p /etc/nginx/ssl
sudo chown -R root:root /etc/nginx/ssl
sudo chmod 700 /etc/nginx/ssl
```

Скопируйте полученные файлы `fullchain.pem` и `privkey.pem` в эту директорию, переименовав их в `nginx.crt` и `nginx.key` соответственно.

### Шаг 3: Обновите конфигурацию Nginx

```ini
# /etc/nginx/sites-available/example.com.conf
server {
    listen 80;
    server_name example.com www.example.com;
    # Перенаправление HTTP → HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com www.example.com;

    ssl_certificate /etc/nginx/ssl/nginx.crt;
    ssl_certificate_key /etc/nginx/ssl/nginx.key;

    # Протоколы и шифры (TLS 1.2+)
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers "EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH";
    ssl_prefer_server_ciphers on;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # HTTP Strict Transport Security (HSTS)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

    # Дополнительные безопасные заголовки
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header X-XSS-Protection "1; mode=block";

    root /var/www/example.com/html;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

**Пояснения к ключевым параметрам**
- `ssl_protocols TLSv1.2 TLSv1.3` – отключаем устаревшие версии.
- `ssl_ciphers` – набор современных шифров, исключая слабые.
- `ssl_stapling` – ускоряет проверку сертификата через OCSP.
- `Strict-Transport-Security` – заставляет браузеры использовать HTTPS.

### Шаг 4: Проверка синтаксиса и перезапуск

```bash
sudo nginx -t   # проверка конфигурации
sudo systemctl reload nginx   # без простоя
```

### Шаг 5: Тестирование сертификата

```bash
# Проверка цепочки и протоколов
openssl s_client -connect localhost:443 -servername example.com -tls1_2 </dev/null | openssl x509 -noout -text | grep "Subject:" -A2
```

## Проверка (Verification)

1. Откройте `https://example.com` в браузере – должно быть зеленое замок‑сообщение.
2. С помощью `curl -v https://example.com` убедитесь, что используется TLS 1.2/1.3 и нет предупреждений о слабых шифрах.
3. Проверьте заголовок HSTS: `curl -I https://example.com | grep Strict-Transport-Security`.
4. Запустите онлайн‑сканер SSL Labs (https://www.ssllabs.com/ssltest/) и убедитесь, что рейтинг **A** или выше.
