---
title: "Kubernetes: CrashLoopBackOff"
service: k8s
severity: critical
error_codes: [EXIT_CODE_1, EXIT_CODE_137, EXIT_CODE_139, SIGKILL, OOMKilled]
tags: [kubernetes, pod, crash, container, orchestration, oom]
---

# Kubernetes: CrashLoopBackOff

## Симптомы

Pod в кластере Kubernetes постоянно перезапускается и не может выйти в состояние Running. Количество рестартов растет экспоненциально. В веб-интерфейсе (Dashboard, Lens, K9s) статус пода отображается как CrashLoopBackOff с красной иконкой. Сервис становится недоступен, пользователи получают 503 Service Unavailable. Время между рестартами увеличивается (backoff: 10s, 20s, 40s, 80s...). Ресурсы cluster могут быть перегружены из-за постоянных попыток рестарта.

## Логи и Сообщения об ошибках

```text
2025-11-28T14:42:33.192847Z INFO  Starting payment-gateway service v2.4.1
2025-11-28T14:42:33.294102Z INFO  Loading configuration from /etc/config/app.yaml
2025-11-28T14:42:33.294847Z ERROR Failed to parse configuration file
Error: yaml: unmarshal errors:
  line 12: cannot unmarshal !!str `${DATAB...` into string
  line 18: field redis.timeout not found in type config.RedisConfig
2025-11-28T14:42:33.295012Z FATAL Configuration validation failed, exiting
2025-11-28T14:42:33.295124Z INFO  Shutdown signal received
thread 'main' panicked at 'called `Result::unwrap()` on an `Err` value: ConfigError', src/main.rs:45:47
stack backtrace:
   0: rust_begin_unwind
             at /rustc/9b00956e5/library/std/src/panicking.rs:584:5
   1: core::panicking::panic_fmt
             at /rustc/9b00956e5/library/core/src/panicking.rs:142:14
   2: core::result::unwrap_failed
             at /rustc/9b00956e5/library/core/src/result.rs:1814:5
   3: payment_gateway::main
             at ./src/main.rs:45
Process exited with code 1
Pod payment-gateway-7d5f8c9b4-xk7m2 in namespace production
Container ID: containerd://a8f3c924b871d4e9f2a6c3b8d7e5f1a0c2b9e4d3
Exit Code: 1
```

```text
[2025-11-28 14:45:18] INFO  [main] com.company.ApiGateway - Starting ApiGateway Application
[2025-11-28 14:45:19] INFO  [main] o.s.boot.SpringApplication - Spring Boot v3.1.5
[2025-11-28 14:45:22] ERROR [main] o.s.boot.diagnostics.LoggingFailureAnalysisReporter
***************************
APPLICATION FAILED TO START
***************************

Description:

Failed to bind properties under 'spring.datasource.url' to java.lang.String:

    Property: spring.datasource.url
    Value: ${DB_CONNECTION_STRING}
    Origin: class path resource [application.yml] - 12:9
    Reason: Could not resolve placeholder 'DB_CONNECTION_STRING' in value "${DB_CONNECTION_STRING}"

Action:

Update your application's configuration
Caused by: java.lang.IllegalArgumentException: Could not resolve placeholder 'DB_CONNECTION_STRING' in value "${DB_CONNECTION_STRING}"
	at org.springframework.util.PropertyPlaceholderHelper.parseStringValue(PropertyPlaceholderHelper.java:180)
	at org.springframework.boot.context.properties.source.ConfigurationPropertySourcesPropertyResolver.getProperty(ConfigurationPropertySourcesPropertyResolver.java:82)
Process terminated with exit code 1
Container api-gateway exited
Reason: Error
Exit Code: 1
Signal: null
```

```text
Nov 28 14:48:52.441 [worker-thread-8] ERROR i.n.u.ResourceLeakDetector - LEAK: ByteBuf.release() was not called before it's garbage-collected.
Recent access records:
Created at:
	io.netty.buffer.PooledByteBufAllocator.newDirectBuffer(PooledByteBufAllocator.java:341)
	io.netty.buffer.AbstractByteBufAllocator.directBuffer(AbstractByteBufAllocator.java:187)
Nov 28 14:48:53.127 [main] FATAL c.c.s.WebServer - Fatal error during startup
java.lang.OutOfMemoryError: Java heap space
	at java.base/java.nio.HeapByteBuffer.<init>(HeapByteBuffer.java:61)
	at java.base/java.nio.ByteBuffer.allocate(ByteBuffer.java:335)
	at com.company.service.CacheManager.loadCache(CacheManager.java:94)
	at com.company.service.WebServer.start(WebServer.java:156)
Dumping heap to /tmp/java_pid1.hprof ...
Heap dump file created [2147483648 bytes in 3.421 secs]
Container killed by Kubernetes (OOMKilled)
Exit Code: 137
Signal: SIGKILL
Reason: OOMKilled
Last State: Terminated
  Reason: OOMKilled
  Exit Code: 137
  Started: 2025-11-28T14:48:49Z
  Finished: 2025-11-28T14:48:53Z
```

## Диагностика

Проверьте статус пода и причину падения:

```bash
# Получите список подов с проблемами
kubectl get pods -A | grep -E 'CrashLoopBackOff|Error|OOMKilled'

# Детальная информация о проблемном поде
kubectl describe pod payment-gateway-7d5f8c9b4-xk7m2 -n production

# Проверьте логи контейнера (текущего)
kubectl logs payment-gateway-7d5f8c9b4-xk7m2 -n production

# Проверьте логи предыдущего контейнера (который упал)
kubectl logs payment-gateway-7d5f8c9b4-xk7m2 -n production --previous

# Если несколько контейнеров в поде
kubectl logs payment-gateway-7d5f8c9b4-xk7m2 -n production -c main-app --previous
```

```bash
# Проверьте events в namespace
kubectl get events -n production --sort-by='.lastTimestamp' | tail -20

# Проверьте ресурсы пода
kubectl top pod payment-gateway-7d5f8c9b4-xk7m2 -n production

# Проверьте лимиты и requests
kubectl get pod payment-gateway-7d5f8c9b4-xk7m2 -n production -o jsonpath='{.spec.containers[*].resources}'
```

```bash
# Проверьте ConfigMaps и Secrets
kubectl get configmap -n production
kubectl describe configmap app-config -n production

# Проверьте переменные окружения
kubectl exec payment-gateway-7d5f8c9b4-xk7m2 -n production -- env

# Проверьте readiness/liveness probes
kubectl get pod payment-gateway-7d5f8c9b4-xk7m2 -n production -o yaml | grep -A 10 "livenessProbe\|readinessProbe"
```

## Решение

**Шаг 1: Определение root cause из логов**

Анализируйте exit code для понимания проблемы:

- **Exit Code 1**: Ошибка приложения (неправильная конфигурация, exception)
- **Exit Code 137**: OOMKilled (нехватка памяти)
- **Exit Code 139**: Segmentation fault (SIGSEGV)
- **Exit Code 143**: SIGTERM (graceful shutdown)

```bash
# Получите последний exit code
kubectl get pod payment-gateway-7d5f8c9b4-xk7m2 -n production -o jsonpath='{.status.containerStatuses[0].lastState.terminated.exitCode}'

# Получите причину
kubectl get pod payment-gateway-7d5f8c9b4-xk7m2 -n production -o jsonpath='{.status.containerStatuses[0].lastState.terminated.reason}'
```

**Шаг 2: Исправление проблем конфигурации**

Если проблема в missing environment variables:

```bash
# Проверьте, что все нужные переменные определены
kubectl get deployment payment-gateway -n production -o yaml | grep -A 20 "env:"

# Обновите deployment с правильными переменными
kubectl set env deployment/payment-gateway -n production DB_CONNECTION_STRING="postgresql://user:pass@db:5432/prod"

# Или отредактируйте напрямую
kubectl edit deployment payment-gateway -n production
```

Если проблема в ConfigMap:

```bash
# Проверьте содержимое ConfigMap
kubectl get configmap app-config -n production -o yaml

# Исправьте ConfigMap
kubectl edit configmap app-config -n production

# Форсируйте обновление подов
kubectl rollout restart deployment/payment-gateway -n production
```

**Шаг 3: Решение проблемы OOMKilled**

Если exit code 137 (OOMKilled):

```bash
# Увеличьте memory limits
kubectl patch deployment payment-gateway -n production -p '
spec:
  template:
    spec:
      containers:
      - name: payment-gateway
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
'

# Проверьте применение
kubectl rollout status deployment/payment-gateway -n production
```

Для Java приложений настройте JVM heap:

```bash
kubectl set env deployment/payment-gateway -n production \
  JAVA_OPTS="-Xms512m -Xmx1536m -XX:MaxMetaspaceSize=256m -XX:+UseG1GC"
```

**Шаг 4: Настройка Health Checks**

Если приложение падает из-за неправильных probes:

```bash
# Создайте или обновите deployment с правильными probes
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-gateway
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-gateway
  template:
    metadata:
      labels:
        app: payment-gateway
    spec:
      containers:
      - name: payment-gateway
        image: company/payment-gateway:v2.4.1
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
EOF
```

**Шаг 5: Debug с временным контейнером**

Если проблема сложная, запустите debug session:

```bash
# Для Kubernetes 1.23+
kubectl debug payment-gateway-7d5f8c9b4-xk7m2 -n production -it --image=busybox --share-processes

# Или создайте pod с тем же манифестом, но с другой командой
kubectl run payment-gateway-debug -n production --image=company/payment-gateway:v2.4.1 --command -- /bin/sh -c "sleep 3600"

# Войдите в контейнер
kubectl exec -it payment-gateway-debug -n production -- /bin/bash

# Проверьте файловую систему, переменные, конфиги
ls -la /etc/config/
cat /etc/config/app.yaml
env | sort
```

**Шаг 6: Мониторинг и алертинг**

```bash
# Создайте PrometheusRule для алертов
cat > crash-loop-alert.yaml <<EOF
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: pod-crash-loop-alert
  namespace: monitoring
spec:
  groups:
  - name: kubernetes.pods
    interval: 30s
    rules:
    - alert: PodCrashLooping
      expr: rate(kube_pod_container_status_restarts_total[15m]) > 0
      for: 5m
      labels:
        severity: critical
      annotations:
        summary: "Pod {{ \$labels.namespace }}/{{ \$labels.pod }} is crash looping"
        description: "Pod has restarted {{ \$value }} times in the last 15 minutes"
EOF

kubectl apply -f crash-loop-alert.yaml
```

**Шаг 7: Профилактика**

- Всегда используйте health checks (liveness + readiness)
- Устанавливайте адекватные resource requests/limits
- Тестируйте deployment в staging окружении
- Используйте init containers для pre-flight checks
- Включите graceful shutdown в приложении
- Логируйте подробно startup sequence
