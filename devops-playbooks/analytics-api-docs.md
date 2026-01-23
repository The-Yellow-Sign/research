# API документация сервиса обработки аналитики (Rust)

Высокопроизводительный сервис для агрегации данных в реальном времени.

## Методы

| Метод | Путь | Описание |
| :--- | :--- | :--- |
| `POST` | `/ingest` | Прием событий для обработки |
| `GET`  | `/health` | Проверка состояния (Liveness) |
| `GET`  | `/metrics`| Метрики в формате Prometheus |

## Пример запроса (Ingest)
```json
{
  "event_type": "page_view",
  "user_id": 12345,
  "timestamp": 1735492200
}
```

## Внутренние структуры
В Rust для десериализации используется `serde`:

```rust
#[derive(Deserialize)]
struct Event {
    event_type: String,
    user_id: u64,
    timestamp: u64,
}
```

> [!NOTE]
> Сервис оптимизирован для работы под нагрузкой > 100k RPS. При возникновении 504 ошибок проверьте состояние [кластера Kafka](kafka-incident-december.md).
