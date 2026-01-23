---
title: "Настройка мониторинга Prometheus"
type: guide
service: prometheus
---

# Настройка мониторинга Prometheus

## Введение

Prometheus – система сбора метрик с поддержкой Pull‑модели, позволяющая централизованно мониторить инфраструктуру и приложения в продакшн‑окружении. Правильная настройка обеспечивает своевременное обнаружение инцидентов и построение графиков в Grafana.

## Требования

- ОС: Linux (Ubuntu 20.04+, CentOS 8+)
- Prometheus версии 2.30+
- Доступ к сети от Prometheus к целевым endpoint‑ам (порт 9090 для UI, 9100+ для exporters)
- `node_exporter` установлен на всех хостах, которые нужно мониторить

## Пошаговая инструкция

### Шаг 1: Установка Prometheus

```bash
# Скачайте последнюю стабильную версию
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz

# Распакуйте и переместите бинарники
tar xzf prometheus-2.45.0.linux-amd64.tar.gz
sudo mv prometheus-2.45.0.linux-amd64/prometheus /usr/local/bin/
sudo mv prometheus-2.45.0.linux-amd64/promtool /usr/local/bin/
sudo mv prometheus-2.45.0.linux-amd64/consoles /etc/prometheus/
sudo mv prometheus-2.45.0.linux-amd64/console_libraries /etc/prometheus/
```

### Шаг 2: Конфигурация `prometheus.yml`

```yaml
# /etc/prometheus/prometheus.yml
global:
  scrape_interval: 15s        # Как часто опрашивать цели
  evaluation_interval: 15s    # Как часто выполнять правила
  scrape_timeout: 10s

# Настраиваем цели (targets)
scrape_configs:
  - job_name: 'node_exporter'
    static_configs:
      - targets: ['10.0.0.1:9100', '10.0.0.2:9100']

  - job_name: 'postgres_exporter'
    static_configs:
      - targets: ['10.0.0.3:9187']
```

**Пояснения**
- `scrape_interval` – частота опроса; в продакшн обычно 15‑30 сек.
- `static_configs` – список IP/портов экспортеров. Можно использовать `dns_sd_configs` или `file_sd_configs` для динамики.

### Шаг 3: Создание systemd‑службы

```ini
# /etc/systemd/system/prometheus.service
[Unit]
Description=Prometheus Monitoring
Wants=network-online.target
After=network-online.target

[Service]
User=prometheus
Group=prometheus
Type=simple
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus/ \
  --web.console.templates=/etc/prometheus/consoles \
  --web.console.libraries=/etc/prometheus/console_libraries

[Install]
WantedBy=multi-user.target
```

```bash
# Создайте пользователя и директории
sudo useradd --no-create-home --shell /usr/sbin/nologin prometheus
sudo mkdir -p /var/lib/prometheus /etc/prometheus
sudo chown -R prometheus:prometheus /var/lib/prometheus /etc/prometheus

# Перезапустите и включите сервис
sudo systemctl daemon-reload
sudo systemctl enable --now prometheus
```

### Шаг 4: Проверка работы

```bash
curl -s http://localhost:9090/-/ready   # должен вернуть 200 OK
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .job, endpoint: .scrapeUrl, health: .health}'
```

## Проверка (Verification)

1. Откройте UI `http://<prometheus_host>:9090/graph` и выполните запрос `up{job="node_exporter"}` – должны увидеть `1` для всех целей.
2. Убедитесь, что в `/var/lib/prometheus/` создаются файлы `chunks_*` и `index` – это база TSDB.
3. Проверьте логи службы: `journalctl -u prometheus -f` – отсутствие ошибок `scrape`.
4. Добавьте простую алерт‑правилу в `rules.yml` и проверьте, что она появляется в UI `Alerts`.
