---
title: "Миграция с Podman обратно на Docker"
service: container-runtime
---

# Почему мы решили вернуться на Docker?

Несмотря на безопасность Podman (rootless), мы столкнулись с рядом проблем совместимости в нашей CI/CD среде на базе GitLab.

### Основные причины
- **Docker Compose**: Поддержка Podman Compose все еще нестабильна для сложных сетей.
- **Performance**: Сборка образов через `buildah` оказалась медленнее, чем нативное использование Docker-демона.
- **Интеграция**: Слишком много скриптов в нашей компании жестко завязаны на `/var/run/docker.sock`.

### Процесс миграции

1. Остановка всех контейнеров: `podman stop --all`.
2. Удаление Podman: `sudo apt remove podman`.
3. Установка Docker:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   ```

> [!NOTE]
> После установки не забудьте добавить вашего пользователя в группу `docker`, чтобы избежать использования `sudo`.

Смотрите также: [Проблемы с правами в Docker](docker-permission-denied.md)
