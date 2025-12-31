# Оптимизация Nginx: Сжатие Gzip и Brotli

Включение сжатия позволяет уменьшить объем передаваемых данных на 60-80%, что значительно ускоряет загрузку страниц для пользователей.

### Настройка Gzip
Добавьте эти строки в блок `http` файла `nginx.conf`:

```nginx
gzip on;
gzip_comp_level 5;
gzip_min_length 256;
gzip_proxied any;
gzip_types
    text/plain
    text/css
    application/json
    application/javascript
    image/svg+xml;
```

### Настройка Brotli (рекомендуется)
Brotli обеспечивает лучшее сжатие, чем Gzip. Требует установки модуля `ngx_brotli`.

```nginx
brotli on;
brotli_comp_level 6;
brotli_types text/plain text/css application/json;
```

> [!TIP]
> Используйте `comp_level` не выше 6, так как дальнейшее увеличение дает минимальный прирост сжатия при резком росте нагрузки на CPU.
