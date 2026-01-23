## Исследование инцидентов через Grafana Loki

Loki — это основная система сбора логов в нашей инфраструктуре. Используйте этот ранбук для быстрого поиска ошибок в микросервисах.

### Шаг 1: Доступ к логам
Откройте Grafana -> Explore -> Выберите `Loki` в качестве источника данных.

### Шаг 2: Полезные запросы (LogQL)

- **Поиск ошибок в конкретном приложении**:
  ```text
  {app="billing-service"} |= "error"
  ```
- **Подсчет количества ошибок в минуту**:
  ```text
  sum by (app) (count_over_time({severity="ERROR"}[1m]))
  ```
- **Поиск по Trace ID (из Jaeger)**:
  ```text
  {namespace="production"} |= "a1b2c3d4"
  ```

### Шаг 3: Проверка состояния Ingestors
Если логи перестали поступать:

```bash
kubectl get pods -n monitoring | grep loki-ingestor
```

> [!WARNING]
> Loki не индексирует содержимое логов, а только метаданные (label). Избегайте использования слишком большого количества уникальных меток (High Cardinality), иначе система может замедлиться.

![Интерфейс Loki в Grafana](path/to/loki_explore.png)

Смотрите также: [Тюнинг Elasticsearch](es-tuning.md)
