## Оптимизация производительности Elasticsearch для тяжелых логов (Loki style)

Когда Elasticsearch начинает "захлебываться" от огромного потока логов, стандартных настроек становится недостаточно. В этом документе собраны рекомендации по тюнингу индексов и JVM.

### Настройка индексов (Index Settings)
Самый эффективный способ ускорить запись — увеличить `index.refresh_interval`. По умолчанию это 1 секунда, что заставляет ES постоянно создавать новые сегменты.

```json
PUT /my-index-pattern/_settings
{
  "index": {
    "refresh_interval": "30s",
    "number_of_replicas": 0,
    "translog.durability": "async"
  }
}
```

> ⚠️ NOTE: Установка реплик в 0 значительно ускоряет индексацию, но делает данные уязвимыми при падении ноды. Используйте это только в процессе первичной загрузки или для некритичных логов.

### Тюнинг JVM
Для Elasticsearch критически важно правильно настроить Heap. Основное правило: не более 50% доступной памяти и не более 31GB (для использования Compressed OOPs).

```bash
# /etc/elasticsearch/jvm.options
-Xms16g
-Xmx16g
-XX:+UseG1GC
-XX:G1ReservePercent=25
```

### Рекомендации по шардированию
Слишком много мелких шардов убивают производительность кластера.
- Целевой размер шарда: **30GB - 50GB**.
- Включайте `ILM` (Index Lifecycle Management) для автоматического переката индексов по размеру, а не по времени.

### Мониторинг
Следите за параметром `indexing_pressure`. Если он растет, значит ES не успевает сбрасывать данные на диск.

![Панель мониторинга в Grafana](path/to/es_performance_dashboard.png)

### Полезные ссылки
- [Tuning for indexing speed](https://www.elastic.co/guide/en/elasticsearch/reference/current/tune-for-indexing-speed.html)
- [Как мы сэкономили 40% ресурсов с Kafka](stream-debug.md)
