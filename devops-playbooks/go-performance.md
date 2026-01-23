# Оптимизация производительности Go-сервисов с помощью Prometheus

Сбор и анализ метрик в реальном времени позволяет находить утечки памяти и неоптимальные участки кода еще до того, как они станут проблемой для пользователей.

Для начала подключите стандартные метрики `prometheus/client_golang`:

```go
import (
    "github.com/prometheus/client_golang/prometheus/promhttp"
    "net/http"
)

func main() {
    http.Handle("/metrics", promhttp.Handler())
    http.ListenAndServe(":2112", nil)
}
```

Одна из самых полезных метрик — `go_memstats_heap_inuse_bytes`. Если этот график постоянно растет без возврата к базовому уровню, у вас есть утечка памяти (memory leak).

### Использование кастомных метрик
Для отслеживания бизнес-логики (например, времени обработки заказа) используйте `Histogram`:

```go
var orderDuration = prometheus.NewHistogram(prometheus.HistogramOpts{
    Name:    "order_process_duration_seconds",
    Help:    "Time spent processing ordering",
    Buckets: prometheus.DefBuckets,
})

func processOrder(w http.ResponseWriter, r *http.Request) {
    start := time.Now()
    // ... логика ...
    duration := time.Since(start).Seconds()
    orderDuration.Observe(duration)
}
```

Не забывайте профилировать приложение под нагрузкой с помощью `pprof`.

> [!TIP]
> Используйте `GOGC` переменную окружения для настройки частоты сборки мусора. Значение `100` — стандарт, `50` — чаще (меньше памяти, больше CPU), `200` — реже.
