# Миграция с Apache HTTPD на Nginx

В этой инструкции описаны основные шаги по переносу конфигураций виртуальных хостов с Apache на Nginx для улучшения производительности и снижения потребления памяти.

## Сравнение конфигураций

| Задача | Apache (.htaccess / httpd.conf) | Nginx (nginx.conf) |
| :--- | :--- | :--- |
| **Document Root** | `DocumentRoot "/var/www/html"` | `root /var/www/html;` |
| **Server Name** | `ServerName example.com` | `server_name example.com;` |
| **Proxy Pass** | `ProxyPass / http://localhost:8080/` | `proxy_pass http://localhost:8080;` |

## Пошаговый процесс

### 1. Перенос правил Rewrite
Apache использует `.htaccess`, который Nginx не поддерживает. Правила нужно переписать в секцию `location`.

```nginx
# В Apache
# RewriteRule ^/news/([0-9]+)$ /news.php?id=$1 [L]

# В Nginx
rewrite ^/news/([0-9]+)$ /news.php?id=$1 last;
```

### 2. Настройка PHP (FastCGI)
Apache обычно использует `mod_php`. Nginx требует `php-fpm`.

```nginx
location ~ \.php$ {
    include snippets/fastcgi-php.conf;
    fastcgi_pass unix:/var/run/php/php8.2-fpm.sock;
}
```

### 3. Проверка и запуск
```bash
nginx -t
systemctl stop apache2
systemctl start nginx
```

> [!WARNING]
> Убедитесь, что все права на директории изменены с пользователя `www-data` (или `apache`) на того, от которого работает Nginx.

Смотрите также: [Тюнинг Nginx](nginx-tuning-compression.md)
