---
title: "Docker: Container Exit Code 137 (OOMKilled)"
service: docker
severity: critical
error_codes: [EXIT_137, SIGKILL, OOMKilled]
tags: [docker, container, oom, memory, orchestration]
---

# Docker: Container Exit Code 137

## Симптомы

Docker контейнер внезапно останавливается с exit code 137. В логах контейнера может не быть явной ошибки. Приложение работает нормально, затем резко падает. Docker inspect показывает OOMKilled: true. Проблема периодически повторяется. Контейнер использует больше памяти, чем выделенный лимит.

## Логи и Сообщения об ошибках

```text
[2025-11-28T16:32:18.392Z] INFO Application started successfully
[2025-11-28T16:32:45.718Z] INFO Processing batch job: 15000 items
[2025-11-28T16:33:12.847Z] WARN Memory usage: 1.8GB / 2GB
[2025-11-28T16:33:15.294Z] INFO Loading data into memory...
Container killed by Docker runtime
Exit Code: 137
OOMKilled: true
Memory limit: 2147483648 (2GB)
Memory usage at death: 2147483648 (2GB)
Process received: SIGKILL
Container ID: a8f3c924b871
Image: company/data-processor:v1.2.3
```

```text
Nov 28 16:34:47 docker-host kernel: [18472.847291] Memory cgroup out of memory: Killed process 18293 (java) total-vm:4194304kB, anon-rss:2097152kB, file-rss:0kB, shmem-rss:0kB
Nov 28 16:34:47 docker-host kernel: [18472.847412] oom_reaper: reaped process 18293 (java), now anon-rss:0kB, file-rss:0kB, shmem-rss:0kB
Nov 28 16:34:47 docker-host dockerd[1247]: time="2025-11-28T16:34:47.192847Z" level=warning msg="Container a8f3c924b871 failed to exit within 10 seconds of signal SIGTERM - using SIGKILL"
Nov 28 16:34:47 docker-host dockerd[1247]: time="2025-11-28T16:34:47.294102Z" level=info msg="Container a8f3c924b871d4e9f2a6c3b8d7e5f1a0 exited with code 137"
Docker container: data-processor
Cgroup: /docker/a8f3c924b871
```

```text
python3: Fatal Python error: Cannot allocate memory
Stack (most recent call first):
  File "/app/processor.py", line 147, in process_large_file
  File "/app/main.py", line 89, in main
Memory requested: 512MB
Available memory: 128MB
Container memory limit: 2GB
RSS usage: 2.1GB (exceeded limit)
Swap disabled
Exit code: 137
Signal: SIGKILL (9)
Container: data-processor-prod
Restart count: 15
Last restart: 2025-11-28T16:34:47Z
```

## Диагностика

```bash
# Проверьте статус контейнера
docker ps -a | grep data-processor
docker inspect data-processor | grep -A 10 "State"
docker inspect data-processor | grep "OOMKilled"

# Посмотрите exit code
docker inspect data-processor --format='{{.State.ExitCode}}'

# Проверьте лимиты памяти
docker stats data-processor --no-stream
docker inspect data-processor | grep -i memory

# Проверьте kernel logs
sudo dmesg | grep -i "out of memory"
sudo journalctl -k | grep -i oom
```

## Решение

**Шаг 1:** Увеличьте memory limit

```bash
docker stop data-processor
docker rm data-processor

docker run -d \
  --name data-processor \
  --memory="4g" \
  --memory-swap="4g" \
  company/data-processor:v1.2.3
```

**Шаг 2:** Для Docker Compose

```yaml
version: '3.8'
services:
  data-processor:
    image: company/data-processor:v1.2.3
    deploy:
      resources:
        limits:
          memory: 4G
        reservations:
          memory: 2G
```

**Шаг 3:** Оптимизируйте Java heap

```bash
docker run -d \
  --name data-processor \
  --memory="4g" \
  -e JAVA_OPTS="-Xms1g -Xmx3g -XX:+UseG1GC" \
  company/data-processor:v1.2.3
```
