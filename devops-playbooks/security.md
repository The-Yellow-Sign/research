title: "Уязвимость в Java-сервисах при использовании старых версий TLS"

# Security Advisory: CVE-2025-XXXXX (Internal)

## Описание
Обнаружена критическая уязвимость в конфигурации TLS на наших Java-микросервисах, использующих Spring Boot. Из-за поддержки устаревших протоколов TLS 1.0 и 1.1 возможна атака типа Man-in-the-Middle (MITM).

## Решение
Необходимо обновить настройки Java Security и конфигурацию Tomcat/Netty.

### Обновление конфигурации
Добавьте следующий параметр в `application.yaml`:

```yaml
server:
  ssl:
    enabled-protocols: TLSv1.2, TLSv1.3
    ciphers: ECDHE-ECDSA-AES128-GCM-SHA256, ECDHE-RSA-AES128-GCM-SHA256
```

### Проверка
Используйте утилиту `openssl` для проверки доступных протоколов:

```bash
openssl s_client -connect my-service.internal:443 -tls1_1
```
Если соединение устанавливается — уязвимость все еще на месте. Вы должны получить `Handshake Failure`.
