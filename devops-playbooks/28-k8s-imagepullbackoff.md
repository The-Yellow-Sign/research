---
title: "Kubernetes: ImagePullBackOff"
type: known_issue
service: k8s
---

# Kubernetes: ImagePullBackOff / ErrImagePull

## Ошибка

```text
Events:
  Type     Reason     Age                From               Message
  ----     ------     ----               ----               -------
  Normal   Scheduled  55s                default-scheduler  Successfully assigned default/my-app-7b4f4b8c4-9z8x2 to node-1
  Normal   Pulling    22s (x2 over 54s)  kubelet            Pulling image "my-registry.com/my-app:v2.0"
  Warning  Failed     22s (x2 over 54s)  kubelet            Failed to pull image "my-registry.com/my-app:v2.0": rpc error: code = Unknown desc = Error response from daemon: manifest for my-registry.com/my-app:v2.0 not found: manifest unknown: manifest unknown
  Warning  Failed     22s (x2 over 54s)  kubelet            Error: ErrImagePull
  Normal   BackOff    8s (x2 over 53s)   kubelet            Back-off pulling image "my-registry.com/my-app:v2.0"
  Warning  Failed     8s (x2 over 53s)   kubelet            Error: ImagePullBackOff
```

## Причина

Kubernetes не может скачать Docker-образ. Основные причины:
1. Неверное имя образа или тег.
2. Образ не существует в реестре.
3. Отсутствуют права доступа (нужен `imagePullSecrets`).

## Решение

Проверьте имя образа и наличие секрета для приватного реестра.

```bash
# Проверка наличия образа
docker pull my-registry.com/my-app:v2.0

# Добавление секрета в Deployment
kubectl patch deployment my-app -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"my-registry-secret"}]}}}}'
```
