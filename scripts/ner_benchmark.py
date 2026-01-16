"""NER Model Benchmark Script (CORRECTED).

Tests NER models on DOCUMENT TEXT (as used during indexing), not on user queries.
Supports MPS (Apple GPU) for acceleration.
"""

import time
import warnings

warnings.filterwarnings("ignore")

# Real document chunks extracted from devops-playbooks
# These simulate what splitter.py feeds to extract_metadata()
TEST_DOCUMENT_CHUNKS = [
    # From 03-nginx-502-bad-gateway.md - contains directives, error codes
    """## Решение: Настройка proxy_next_upstream

Директива `proxy_next_upstream` позволяет Nginx автоматически повторить запрос
на другом upstream сервере при ошибках. Это критически важно для High Availability.

```nginx
upstream backend {
    server 10.0.0.1:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.2:8080 max_fails=3 fail_timeout=30s;
    server 10.0.0.3:8080 backup;
}

server {
    location / {
        proxy_pass http://backend;
        proxy_next_upstream error timeout http_502 http_503 http_504;
        proxy_next_upstream_timeout 10s;
        proxy_next_upstream_tries 3;
    }
}
```

При ошибках 502/503/504 Nginx автоматически попробует следующий сервер.""",
    # From 04-redis-out-of-memory.md - contains commands, parameters
    """## Диагностика OOM в Redis

Проверьте текущее использование памяти:

```bash
redis-cli INFO memory | grep used_memory
redis-cli CONFIG GET maxmemory
redis-cli CONFIG GET maxmemory-policy
```

Если `used_memory` близко к `maxmemory`, Redis начнёт выселять ключи
согласно политике `maxmemory-policy`.

Рекомендуемые политики:
- `volatile-lru` — выселяет ключи с TTL по LRU
- `allkeys-lru` — выселяет любые ключи по LRU
- `noeviction` — возвращает ошибку OOM (опасно!)""",
    # From 02-k8s-crashloopbackoff.md - contains k8s entities
    """## Kubernetes CrashLoopBackOff

Pod падает с ошибкой CrashLoopBackOff. Проверьте логи:

```bash
kubectl describe pod my-app-5d8f9b7c6d-abc12 -n production
kubectl logs my-app-5d8f9b7c6d-abc12 -n production --previous
```

Частые причины:
- **OOMKilled (exit code 137)**: контейнер превысил memory limit
- **Error (exit code 1)**: ошибка в приложении
- **ImagePullBackOff**: не удалось скачать образ

Решение для OOMKilled:
```yaml
resources:
  limits:
    memory: "512Mi"
  requests:
    memory: "256Mi"
```""",
    # From ansible-redis-release.md - contains version, technology
    """## Ansible Role Redis v2.5.0 Release Notes

Новые возможности в версии v2.5.0:

1. **Sentinel Configuration**: Теперь можно настраивать параметры Sentinel:
   - `redis_sentinel_quorum: 2`
   - `redis_sentinel_down_after_milliseconds: 30000`
   - `redis_sentinel_parallel_syncs: 1`

2. **TLS Support**: Добавлена поддержка TLS 1.3
   - `redis_tls_enabled: true`
   - `redis_tls_cert_file: /etc/redis/tls/redis.crt`

3. **Cluster Mode**: Улучшена поддержка Redis Cluster
   - `redis_cluster_enabled: true`
   - `redis_cluster_replicas: 1`""",
    # From db-migration-rds.md - contains services, technologies
    """## Миграция MySQL → PostgreSQL с AWS DMS

При использовании AWS Database Migration Service (DMS) для миграции из MySQL в PostgreSQL
рекомендуется следующий порядок действий:

1. Создайте replication instance в AWS DMS
2. Настройте source endpoint (MySQL) и target endpoint (PostgreSQL)
3. **ВАЖНО**: Создавайте индексы на целевой БД только ПОСЛЕ завершения full load
   - При создании индексов ДО миграции производительность INSERT падает на 60-80%
   - DMS сам создаст primary keys, но не secondary indexes

```bash
aws dms create-replication-task \\
    --replication-instance-arn $INSTANCE_ARN \\
    --source-endpoint-arn $MYSQL_ENDPOINT \\
    --target-endpoint-arn $POSTGRES_ENDPOINT \\
    --migration-type full-load-and-cdc
```""",
    # From sre-handbook.md - contains parameters, procedures
    """## On-Call Response Time SLA

Согласно SRE Handbook, время реакции на инциденты:

| Priority | Description | Response Time | ACK Time |
|----------|-------------|---------------|----------|
| P0 | Critical (production down) | 5 min | 15 min |
| P1 | High (major feature broken) | 15 min | 1 hour |
| P2 | Medium (degraded performance) | 1 hour | 4 hours |
| P3 | Low (minor issue) | 4 hours | 24 hours |

Все сервисы должны логировать в JSON формате с обязательными полями:
- `timestamp` — ISO 8601
- `level` — DEBUG/INFO/WARN/ERROR
- `message` — текст сообщения
- `app_name` — название сервиса
- `env` — окружение (prod/staging/dev)
- `trace_id` — ID для distributed tracing""",
    # From linux-network-tuning.md - contains sysctl parameters
    """## Тюнинг сетевого стека Linux

Для высоконагруженных серверов рекомендуется настроить sysctl:

```bash
# Размер очереди пакетов, ожидающих обработки
sysctl -w net.core.netdev_max_backlog=65536

# Размер буферов TCP
sysctl -w net.core.rmem_max=16777216
sysctl -w net.core.wmem_max=16777216

# Congestion control algorithm
sysctl -w net.ipv4.tcp_congestion_control=bbr

# Enable TCP Fast Open
sysctl -w net.ipv4.tcp_fastopen=3
```

Алгоритм `bbr` (Bottleneck Bandwidth and RTT) рекомендуется вместо стандартного CUBIC
для современных сетей с высокой пропускной способностью.""",
    # From terraform-aws-auth.md - contains environment variables
    """## Аутентификация Terraform в AWS и GCP

### AWS Authentication
```bash
export AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
export AWS_DEFAULT_REGION="eu-west-1"
```

### GCP Authentication (Service Account JSON)
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account.json"
export GOOGLE_PROJECT="my-project-123"
```

Для CI/CD рекомендуется использовать:
- AWS: IAM Roles for Service Accounts (IRSA) в EKS
- GCP: Workload Identity Federation""",
]

# Expected entities for validation (ground truth)
EXPECTED_ENTITIES = [
    {
        "directive": ["proxy_next_upstream"],
        "error_code": ["502", "503", "504"],
        "service": ["nginx"],
    },
    {
        "service": ["redis"],
        "command": ["redis-cli"],
        "parameter": ["maxmemory", "maxmemory-policy"],
    },
    {
        "technology": ["kubernetes"],
        "error_code": ["OOMKilled", "137", "CrashLoopBackOff"],
        "command": ["kubectl"],
    },
    {
        "technology": ["ansible"],
        "service": ["redis"],
        "version": ["v2.5.0"],
        "parameter": ["sentinel"],
    },
    {
        "service": ["mysql", "postgresql"],
        "technology": ["aws dms"],
        "command": ["aws"],
    },
    {
        "parameter": ["Response Time", "ACK Time"],
        "environment": ["prod", "staging"],
    },
    {
        "command": ["sysctl"],
        "parameter": [
            "netdev_max_backlog",
            "tcp_congestion_control",
            "bbr",
        ],
    },
    {
        "technology": ["terraform"],
        "service": ["aws", "gcp"],
        "environment": ["CI/CD"],
    },
]


def get_device():
    """Определяет лучшее доступное устройство: MPS > CUDA > CPU."""
    try:
        import torch

        if torch.backends.mps.is_available():
            print("   🍎 Using MPS (Apple GPU)")
            return "mps"
        elif torch.cuda.is_available():
            print("   🔥 Using CUDA (NVIDIA GPU)")
            return "cuda"
    except ImportError:
        pass
    print("   💻 Using CPU")
    return "cpu"


def test_gliner_medium():
    """Test with GLiNER Medium model on document text."""
    print("\n" + "=" * 60)
    print("🔬 Testing GLiNER Medium (urchade/gliner_medium-v2.1)")
    print("=" * 60)

    try:
        from gliner import GLiNER
    except ImportError:
        print("❌ gliner package not installed.")
        return None, 0

    labels = [
        "service",
        "technology",
        "command",
        "directive",
        "parameter",
        "error_code",
        "file_path",
        "version",
        "environment",
    ]

    device = get_device()

    try:
        model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")
        if device in ("mps", "cuda"):
            model = model.to(device)
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        return None, 0

    results = []
    start_time = time.time()

    for i, chunk in enumerate(TEST_DOCUMENT_CHUNKS):
        try:
            # Truncate as done in real extractor
            text = chunk[:2000]
            entities = model.predict_entities(text, labels, threshold=0.35)
            extracted = {}
            for e in entities:
                label = e["label"]
                if label not in extracted:
                    extracted[label] = []
                extracted[label].append(e["text"])

            results.append({"chunk_id": i + 1, "entities": extracted})
            print(f"\n{i + 1}. Chunk preview: {chunk[:60].replace(chr(10), ' ')}...")
            print(f"   → {extracted if extracted else '(no entities)'}")
        except Exception as e:
            print(f"\n{i + 1}. Error: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed:.2f}s ({elapsed / len(TEST_DOCUMENT_CHUNKS):.2f}s per chunk)")

    return results, elapsed


def test_gliner_large():
    """Test with GLiNER Large model on document text."""
    print("\n" + "=" * 60)
    print("🔬 Testing GLiNER Large (urchade/gliner_large-v2.1)")
    print("=" * 60)

    try:
        from gliner import GLiNER
    except ImportError:
        print("❌ gliner package not installed.")
        return None, 0

    labels = [
        "service",
        "technology",
        "command",
        "directive",
        "parameter",
        "error_code",
        "file_path",
        "version",
        "environment",
    ]

    device = get_device()

    try:
        print("   ⏳ Loading model (this may take a while for Large)...")
        model = GLiNER.from_pretrained("urchade/gliner_large-v2.1")
        if device in ("mps", "cuda"):
            model = model.to(device)
        print("   ✅ Model loaded!")
    except Exception as e:
        print(f"❌ Failed to load GLiNER Large: {e}")
        return None, 0

    results = []
    start_time = time.time()

    for i, chunk in enumerate(TEST_DOCUMENT_CHUNKS):
        try:
            text = chunk[:2000]
            entities = model.predict_entities(text, labels, threshold=0.35)
            extracted = {}
            for e in entities:
                label = e["label"]
                if label not in extracted:
                    extracted[label] = []
                extracted[label].append(e["text"])

            results.append({"chunk_id": i + 1, "entities": extracted})
            print(f"\n{i + 1}. Chunk preview: {chunk[:60].replace(chr(10), ' ')}...")
            print(f"   → {extracted if extracted else '(no entities)'}")
        except Exception as e:
            print(f"\n{i + 1}. Error: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed:.2f}s ({elapsed / len(TEST_DOCUMENT_CHUNKS):.2f}s per chunk)")

    return results, elapsed


def test_gliner2():
    """Test with GLiNER2 Base model on document text."""
    print("\n" + "=" * 60)
    print("🔬 Testing GLiNER2 (fastino/gliner2-base-v1)")
    print("=" * 60)

    try:
        from gliner2 import GLiNER2
    except ImportError:
        print("❌ gliner2 package not installed.")
        return None, 0

    labels = [
        "service",
        "technology",
        "command",
        "directive",
        "parameter",
        "error_code",
        "file_path",
        "version",
        "environment",
    ]

    try:
        model = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
    except Exception as e:
        print(f"❌ Failed to load GLiNER2: {e}")
        return None, 0

    results = []
    start_time = time.time()

    for i, chunk in enumerate(TEST_DOCUMENT_CHUNKS):
        try:
            text = chunk[:2000]
            result = model.extract_entities(text, labels, threshold=0.35)
            extracted = {}
            entities_dict = result.get("entities", result) if isinstance(result, dict) else {}
            for label, texts in entities_dict.items():
                if isinstance(texts, list):
                    extracted[label] = texts
            extracted = {k: v for k, v in extracted.items() if v}

            results.append({"chunk_id": i + 1, "entities": extracted})
            print(f"\n{i + 1}. Chunk preview: {chunk[:60].replace(chr(10), ' ')}...")
            print(f"   → {extracted if extracted else '(no entities)'}")
        except Exception as e:
            print(f"\n{i + 1}. Error: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed:.2f}s ({elapsed / len(TEST_DOCUMENT_CHUNKS):.2f}s per chunk)")

    return results, elapsed


def test_gliner2_large():
    """Test with GLiNER2 Large model on document text."""
    print("\n" + "=" * 60)
    print("🔬 Testing GLiNER2 Large (fastino/gliner2-large-v1)")
    print("=" * 60)

    try:
        from gliner2 import GLiNER2
    except ImportError:
        print("❌ gliner2 package not installed.")
        return None, 0

    labels = [
        "service",
        "technology",
        "command",
        "directive",
        "parameter",
        "error_code",
        "file_path",
        "version",
        "environment",
    ]

    try:
        print("   ⏳ Loading GLiNER2 Large model...")
        model = GLiNER2.from_pretrained("fastino/gliner2-large-v1")
        print("   ✅ Model loaded!")
    except Exception as e:
        print(f"❌ GLiNER2 Large failed: {e}")
        return None, 0

    results = []
    start_time = time.time()

    for i, chunk in enumerate(TEST_DOCUMENT_CHUNKS):
        try:
            text = chunk[:2000]
            result = model.extract_entities(text, labels, threshold=0.35)
            extracted = {}
            entities_dict = result.get("entities", result) if isinstance(result, dict) else {}
            for label, texts in entities_dict.items():
                if isinstance(texts, list):
                    extracted[label] = texts
            extracted = {k: v for k, v in extracted.items() if v}

            results.append({"chunk_id": i + 1, "entities": extracted})
            print(f"\n{i + 1}. Chunk preview: {chunk[:60].replace(chr(10), ' ')}...")
            print(f"   → {extracted if extracted else '(no entities)'}")
        except Exception as e:
            print(f"\n{i + 1}. Error: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed:.2f}s ({elapsed / len(TEST_DOCUMENT_CHUNKS):.2f}s per chunk)")

    return results, elapsed


def _extract_zeroner_entities(model, tokenizer, text, entity_descriptions, device):  # noqa: C901
    """Extract entities using ZeroNER."""
    import torch

    extracted = {}
    for label, description in entity_descriptions.items():
        prompt = f"{text} [SEP] {description}"
        inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)

        if device in ("mps", "cuda"):
            inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)

        predictions = torch.argmax(outputs.logits, dim=2)
        predicted_tags = [model.config.id2label[t.item()] for t in predictions[0]]
        tokens = tokenizer.convert_ids_to_tokens(inputs["input_ids"][0].cpu())

        # Extract entities from BIO tags
        current_entity = []
        try:
            sep_idx = tokens.index("[SEP]")
        except ValueError:
            sep_idx = len(tokens)

        for token, tag in zip(tokens[:sep_idx], predicted_tags[:sep_idx], strict=False):
            if token in ["[CLS]", "[SEP]", "[PAD]"]:
                continue

            if tag.startswith("B-"):
                if current_entity:
                    entity_text = tokenizer.convert_tokens_to_string(current_entity).strip()
                    if entity_text and len(entity_text) > 1:
                        if label not in extracted:
                            extracted[label] = []
                        if entity_text not in extracted[label]:
                            extracted[label].append(entity_text)
                current_entity = [token]
            elif tag.startswith("I-") and current_entity:
                current_entity.append(token)
            else:
                if current_entity:
                    entity_text = tokenizer.convert_tokens_to_string(current_entity).strip()
                    if entity_text and len(entity_text) > 1:
                        if label not in extracted:
                            extracted[label] = []
                        if entity_text not in extracted[label]:
                            extracted[label].append(entity_text)
                current_entity = []
    return extracted


def test_zeroner():
    """Test with ZeroNER model (description-driven NER)."""
    print("\n" + "=" * 60)
    print("🔬 Testing ZeroNER (disi-unibo-nlp/zeroner-base)")
    print("=" * 60)

    try:
        from transformers import AutoModelForTokenClassification, AutoTokenizer
    except ImportError:
        print("❌ transformers or torch not installed.")
        return None, 0

    device = get_device()

    try:
        print("   ⏳ Loading ZeroNER model...")
        tokenizer = AutoTokenizer.from_pretrained("disi-unibo-nlp/zeroner-base")
        model = AutoModelForTokenClassification.from_pretrained("disi-unibo-nlp/zeroner-base")

        if device in ("mps", "cuda"):
            model = model.to(device)

        print("   ✅ Model loaded!")
    except Exception as e:
        print(f"❌ Failed to load ZeroNER: {e}")
        return None, 0

    # Entity type descriptions for ZeroNER
    entity_descriptions = {
        "service": "Software service or database like nginx, redis, kafka, postgresql",
        "technology": "Technology platform like kubernetes, docker, ansible, terraform",
        "command": "Command-line tool like kubectl, sysctl, docker, redis-cli",
        "directive": "Configuration directive like proxy_next_upstream, maxmemory",
        "parameter": "Configuration parameter like timeout, max_fails, buffer_size",
        "error_code": "Error code like 502, OOMKilled, Connection refused",
    }

    results = []
    start_time = time.time()

    print("   ⚠️  ZeroNER is slow (processes each entity type separately)...")

    for i, chunk in enumerate(TEST_DOCUMENT_CHUNKS):
        try:
            text = chunk[:500]  # ZeroNER is slow, use smaller chunks
            extracted = _extract_zeroner_entities(
                model, tokenizer, text, entity_descriptions, device
            )

            results.append({"chunk_id": i + 1, "entities": extracted})
            print(f"\n{i + 1}. Chunk preview: {chunk[:60].replace(chr(10), ' ')}...")
            print(f"   → {extracted if extracted else '(no entities)'}")
        except Exception as e:
            print(f"\n{i + 1}. Error: {e}")

    elapsed = time.time() - start_time
    print(f"\n⏱️  Total time: {elapsed:.2f}s ({elapsed / len(TEST_DOCUMENT_CHUNKS):.2f}s per chunk)")

    return results, elapsed


if __name__ == "__main__":
    print("=" * 60)
    print("  NER MODEL BENCHMARK (DOCUMENT TEXT)")
    print(f"  Testing on {len(TEST_DOCUMENT_CHUNKS)} real document chunks")
    print("  (Simulating indexing-time metadata extraction)")
    print("=" * 60)

    # Test GLiNER Medium
    gliner_results, gliner_time = test_gliner_medium()

    # Test GLiNER Large
    gliner_large_results, gliner_large_time = test_gliner_large()

    # Test GLiNER2 Base
    gliner2_results, gliner2_time = test_gliner2()

    # Test GLiNER2 Large
    gliner2_large_results, gliner2_large_time = test_gliner2_large()

    # Test ZeroNER
    zeroner_results, zeroner_time = test_zeroner()

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    if gliner_results:
        print(
            f"GLiNER Medium: {gliner_time:.2f}s total "
            f"({gliner_time / len(TEST_DOCUMENT_CHUNKS):.2f}s/chunk)"
        )
    else:
        print("GLiNER Medium: Failed")

    if gliner_large_results:
        print(
            f"GLiNER Large:  {gliner_large_time:.2f}s total "
            f"({gliner_large_time / len(TEST_DOCUMENT_CHUNKS):.2f}s/chunk)"
        )
    else:
        print("GLiNER Large:  Failed/Skipped")

    if gliner2_results:
        print(
            f"GLiNER2 Base:  {gliner2_time:.2f}s total "
            f"({gliner2_time / len(TEST_DOCUMENT_CHUNKS):.2f}s/chunk)"
        )
    else:
        print("GLiNER2 Base:  Not installed")

    if gliner2_large_results:
        print(
            f"GLiNER2 Large: {gliner2_large_time:.2f}s total "
            f"({gliner2_large_time / len(TEST_DOCUMENT_CHUNKS):.2f}s/chunk)"
        )
    else:
        print("GLiNER2 Large: Failed/Skipped")

    if zeroner_results:
        print(
            f"ZeroNER:       {zeroner_time:.2f}s total "
            f"({zeroner_time / len(TEST_DOCUMENT_CHUNKS):.2f}s/chunk)"
        )
    else:
        print("ZeroNER:       Failed/Skipped")

    print("\n💡 Recommendation: Use MPS for 2-5x speedup on Apple Silicon.")
