---
title: "Docker: Permission Denied (Unix Socket)"
type: known_issue
service: docker
---

# Docker: Got permission denied while trying to connect to the Docker daemon socket

## Ошибка

```text
docker: Got permission denied while trying to connect to the Docker daemon socket at unix:///var/run/docker.sock: Post "http://%2Fvar%2Frun%2Fdocker.sock/v1.24/containers/create": dial unix /var/run/docker.sock: connect: permission denied.
See 'docker run --help'.
```

## Причина

Текущий пользователь не имеет прав на доступ к сокету Docker (`/var/run/docker.sock`). Обычно этот файл принадлежит пользователю `root` и группе `docker`.

## Решение

Добавьте текущего пользователя в группу `docker`.

```bash
sudo usermod -aG docker $USER
```
*После выполнения команды необходимо перелогиниться (logout/login) или выполнить `newgrp docker`.*
