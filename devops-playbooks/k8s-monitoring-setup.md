title: "Мониторинг K8s: Prometheus + Grafana"

# Базовая настройка мониторинга через Prometheus Operator

Эта инструкция поможет вам развернуть полноценный стек мониторинга в вашем кластере Kubernetes всего за несколько минут.

### Шаг 1: Установка Helm Chart
Мы используем официальный чарт `kube-prometheus-stack`.

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace
```

### Шаг 2: Проброс портов (Port Forwarding)
Для быстрого доступа к интерфейсам без настройки Ingress:

- **Prometheus**: `kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090`
- **Grafana**: `kubectl port-forward -n monitoring svc/monitoring-grafana 3000`

> [!NOTE]
> Логин по умолчанию для Grafana: `admin`, пароль: `prom-operator`.

### Шаг 3: Добавление алертов в Slack
Отредактируйте `values.yaml` для Alertmanager:

```yaml
alertmanager:
  config:
    global:
      slack_api_url: 'https://hooks.slack.com/services/XXXXX'
    route:
      receiver: 'slack-notifications'
    receivers:
    - name: 'slack-notifications'
      slack_configs:
      - channel: '#alerts'
        send_resolved: true
```

![Общий вид дашборда мониторинга](path/to/k8s_grafana_main.png)

### Полезные команды
- `kubectl get servicemonitors -n monitoring` — просмотр настроенных целей сбора метрик.
- `kubectl top nodes` — быстрая проверка ресурсов через Metrics Server.
