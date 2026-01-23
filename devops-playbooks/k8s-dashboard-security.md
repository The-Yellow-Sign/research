---
service: kubernetes
title: "Уязвимость: Незащищенный доступ к Kubernetes Dashboard"
tags: [security, k8s, dashboard]
severity: critical
---

# Security Advisory: Публичный доступ к K8s Dashboard без аутентификации

## Описание
Обнаружено, что в некоторых кластерах Kubernetes Dashboard развернут с флагом `--enable-skip-login` и доступен через публичный Ingress. Это позволяет любому пользователю получить права `cluster-admin`.

## Риски
- Полный контроль над кластером.
- Кража секретов (Secrets), включая ключи API и пароли БД.
- Запуск вредоносных подов (криптомайнеры).

## Исправление

### 1. Отключение возможности пропуска логина
Удалите аргумент `--enable-skip-login` из манифеста Deployment-а Dashboard.

### 2. Настройка Ingress (Whitelisting)
Ограничьте доступ только для корпоративной VPN.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  annotations:
    nginx.ingress.kubernetes.io/whitelist-source-range: "10.0.0.0/8, 172.16.0.0/12"
```

### 3. Рекомендуемое решение
**Удалите Kubernetes Dashboard** и используйте более безопасные инструменты, такие как `k9s` или `Lens` с локальной аутентификацией.

```bash
kubectl delete ns kubernetes-dashboard
```

> [!IMPORTANT]
> После исправления рекомендуется провести ротацию ВСЕХ секретов в кластере, так как они могли быть скомпрометированы.
