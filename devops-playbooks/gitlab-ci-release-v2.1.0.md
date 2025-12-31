# Release Notes: CI/CD Pipeline v2.1.0 (GitLab + Ansible)

Обновление системы автоматизации деплоя. Основной упор сделан на безопасность и скорость сборки образов.

## Что нового?

### GitLab CI
- **Cachable Layers**: Добавлена поддержка `docker-container` драйвера для `buildx`, что ускорило сборку на 40%.
- **OIDC Auth**: Теперь пайплайны авторизуются в AWS через OpenID Connect вместо долгоживущих ключей.

### Ansible Roles
- Обновлена роль `ansible-role-nginx`: добавлена поддержка HTTP/3 (QUIC).
- Роль `ansible-role-postgresql` теперь поддерживает автоматический тюнинг `huge_pages`.

## Исправления
- Исправлена ошибка, при которой `cleanup` стадия не срабатывала при отмене пайплайна.
- Подавлены варнинги в Ansible при работе с Python 3.11.

## Breaking Changes
- Удалена поддержка Terraform 0.12. Переведите все стейты на 1.x.

```yaml
# New CI syntax for AWS login
aws-auth:
  id_token:
    aws_token:
      aud: https://gitlab.com
```

---
*Документация:* [Wiki: CI structure](https://wiki.company.com/ci)
![Build Time Chart](graphs/release_v2_1_metrics.png)
