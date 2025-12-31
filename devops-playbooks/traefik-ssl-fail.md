# Ошибки SSL/TLS в Traefik при использовании Let's Encrypt

## Симптомы
Браузер возвращает ошибку `Internal Server Error` или `Connection is not secure` при попытке доступа к сервису через Traefik. В логах Traefik видны ошибки выпуска сертификата.

## Анализ логов

### Ошибка 429 (Rate Limit)
Если вы слишком часто перезапускали контейнеры, Let's Encrypt может заблокировать ваш домен.

```text
time="2024-12-25T12:00:00Z" level=error msg="Error creating new order: acme: error: 429 :: POST :: https://acme-v02.api.letsencrypt.org/acme/new-order :: urn:ietf:params:acme:error:rateLimited :: Your IP, domain, or account has reached a rate limit"
```

### Ошибка DNS Challenge
Если используется `dnsChallenge`, убедитесь, что API ключ провайдера (Cloudflare, AWS Route53) верный.

```text
time="2024-12-25T12:05:00Z" level=error msg="Error constructing DNS provider: cloudflare: some environment variables are missing: CLOUDFLARE_EMAIL,CLOUDFLARE_API_KEY"
```

## Список действий для исправления

- **Проверьте права доступа к файлу acme.json**:
  - Файл должен иметь права `600`.
  - `chmod 600 acme.json`
- **Проверьте доступность порта 80**:
  - Если используется `httpChallenge`, порт 80 должен быть открыт "наружу".
- **Используйте Staging**:
  - При отладке всегда используйте `caServer: "https://acme-staging-v02.api.letsencrypt.org/directory"`.

> [!WARNING]
> Никогда не удаляйте файл `acme.json` без резервной копии, если у вас уже есть рабочие сертификаты.

Смотрите также: [Инструкция по Nginx TLS](nginx-tls-security.md)
