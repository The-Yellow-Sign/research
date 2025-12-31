---
service: MongoDB, Kubernetes
title: Миграция MongoDB из On-Premise в K8s (StatefulSet)
tags: database, migration, k8s, mongodb
severity: high
---

# Гайд по миграции базы данных MongoDB в кластер Kubernetes

Этот документ описывает процесс переноса данных из физических серверов в облачную инфраструктуру с использованием Helm-чарта Bitnami.

## Архитектура целевого решения
Мы используем `StatefulSet` с 3 репликами. Каждый под имеет свой `PersistentVolumeClaim` (PVC).

![MongoDB K8s Layout](path/to/k8s_mongo.png)

## Подготовка инфраструктуры (Terraform)
Убедитесь, что настроены StorageClass для вашего облака (EBS/GCP PD).

```yaml
# values.yaml for MongoDB Helm
architecture: replicaset
replicaCount: 3
persistence:
  enabled: true
  size: 100Gi
```

## Процесс миграции

### 1. Создание бэкапа (Dump)
На старом сервере выполняем:
```bash
mongodump --host 10.10.1.5 --db production_db --out /tmp/mongo_backup
```

### 2. Передача данных в K8s
Копируем дамп внутрь пода основной реплики:
```bash
kubectl cp /tmp/mongo_backup mongodb-0:/tmp/mongo_backup
```

### 3. Восстановление (Restore)
```bash
kubectl exec -it mongodb-0 -- mongorestore /tmp/mongo_backup
```

## Валидация
- Проверить статус репликации: `rs.status()`
- Проверить наличие индексов.
- Запустить синтетические тесты на чтение/запись.

> [!CAUTION]
> Перед началом миграции переведите приложение в режим "Read-Only", чтобы избежать расхождения данных.

### TODO
- Настроить бэкапы через Velero.
- Оптимизировать параметры `wiredTiger` cache size.
