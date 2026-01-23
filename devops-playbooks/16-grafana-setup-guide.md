---
title: "Настройка Grafana для визуализации метрик"
type: guide
service: grafana
---

# Настройка Grafana для визуализации метрик

## Введение

Grafana – популярный инструмент для построения дашбордов на основе метрик из Prometheus, Loki и других источников. Правильная настройка обеспечивает быстрый доступ к аналитике, упрощает диагностику и позволяет создавать алерты.

## Требования

- ОС: Linux (Ubuntu 20.04+, CentOS 8+)
- Grafana версии 9.0+
- Доступ к Prometheus (порт 9090) и/или Loki (порт 3100)
- Порт 3000 открыт для веб‑доступа

## Пошаговая инструкция

### Шаг 1: Установка Grafana

```bash
# Добавляем репозиторий
sudo apt-get install -y software-properties-common wget gnupg
wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -
echo "deb https://packages.grafana.com/oss/deb stable main" | sudo tee /etc/apt/sources.list.d/grafana.list

sudo apt-get update
sudo apt-get install -y grafana
```

### Шаг 2: Запуск и включение сервиса

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now grafana-server
```

### Шаг 3: Первичная конфигурация (grafana.ini)

```ini
# /etc/grafana/grafana.ini
[server]
protocol = http
http_port = 3000
domain = grafana.example.com
# Включаем HTTPS через reverse‑proxy (если нужен)
# root_url = https://grafana.example.com

[security]
admin_user = admin
admin_password = StrongGrafanaPass123

[auth.anonymous]
enabled = false
```

### Шаг 4: Добавление источников данных

1. Откройте UI `http://<host>:3000` и войдите под `admin`.
2. Перейдите **Configuration → Data Sources → Add data source**.
3. Выберите **Prometheus** и укажите URL `http://prometheus-host:9090`.
4. Сохраните и проверьте **Test** – должно вернуть `Data source is working`.
5. При необходимости добавьте **Loki** (URL `http://loki-host:3100`).

### Шаг 5: Создание базового дашборда

```json
{
  "title": "System Overview",
  "panels": [
    {
      "type": "graph",
      "title": "CPU Usage",
      "targets": [{"expr": "100 - (avg by (instance) (irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100"}]
    },
    {
      "type": "graph",
      "title": "Memory Usage",
      "targets": [{"expr": "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100"}]
    }
  ]
}
```

Сохраните как **System Overview** и сделайте **Share → Snapshot** для быстрой проверки.

## Проверка (Verification)

1. Откройте дашборд в браузере – графики должны отображать актуальные метрики.
2. Перейдите **Server Admin → Users** и убедитесь, что пароль изменён от значения по‑умолчанию.
3. Проверьте логи Grafana: `journalctl -u grafana-server -f` – отсутствие ошибок `Failed to load datasource`.
4. Настройте простой алерт в дашборде (CPU > 90%) и проверьте, что он появляется в **Alerting → Alerts**.
