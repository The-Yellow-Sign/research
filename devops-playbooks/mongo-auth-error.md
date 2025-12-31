# Проблемы с аутентификацией в MongoDB при запуске через Docker Compose

## Симптомы
После поднятия стека через `docker-compose up -d`, приложение не может подключиться к базе данных, выдавая ошибку `Authentication failed`. При этом в логах MongoDB видны попытки подключения, но авторизация отклоняется.

## Типичные ошибки (Logs)
```text
2025-12-29T15:10:22.442+0000 I ACCESS   [conn12] Authentication failed for user 'admin' on 'admin' from client '172.18.0.3:44122'; Connection rejected: Authentication failed
2025-12-29T15:10:25.881+0000 I NETWORK  [conn12] end connection 172.18.0.3:44122 (0 connections now open)
```

## Причины и решения

### 1. Переменные окружения
Проверьте, что в `docker-compose.yaml` установлены правильные переменные для инициализации первого пользователя.

```yaml
services:
  mongodb:
    image: mongo:latest
    environment:
      - MONGO_INITDB_ROOT_USERNAME=admin
      - MONGO_INITDB_ROOT_PASSWORD=secretpassword
```

> ⚠️ WARNING: Эти переменные работают ТОЛЬКО при первом запуске (когда папка данных пуста). Если вы изменили пароль в YAML после того, как база уже была создана, он не обновится в БД.

### 2. Специфические команды (Устаревшие)
Если вы используете старые образы (mongo < 3.6), убедитесь, что вы не используете флаг `--auth` без предварительного создания пользователя.
В более новых версиях рекомендуется использовать встроенные механизмы инициализации.

```bash
# ПРЕДУПРЕЖДЕНИЕ: Использование mongo shell (deprecated)
# В новых версиях используйте mongosh
mongo admin -u admin -p --eval "db.auth('admin', 'password')"
```

### 3. Формат Connection String
Приложение на Node.js или Python может требовать указания `authSource`.

```text
mongodb://admin:secretpassword@mongodb:27017/mybase?authSource=admin
```

## Как сбросить данные для пересоздания пользователя
Если вы запутались в паролях на этапе разработки:
1. Остановите контейнеры: `docker-compose down`.
2. Удалите volume (ВНИМАНИЕ: данные будут потеряны): `docker volume rm project_mongo_data`.
3. Запустите заново: `docker-compose up -d`.

### Полезные ссылки
- [Docker Hub: MongoDB Official Image](https://hub.docker.com/_/mongo)
- [Проблемы с дисками в Docker](docker-permission-denied.md)
