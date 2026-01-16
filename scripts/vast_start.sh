#!/bin/bash
set -e

# ==========================================
# Vast.ai On-Start Script (Corrected for Qwen3-Next)
# Hardware: Requires ~48GB+ VRAM (e.g. 2x RTX 3090/4090 or 1x A6000/A100)
# ==========================================

# --- CONFIGURATION (Jan 2026 Compatible) ---
MILVUS_VER="2.6.8"
ETCD_VER="v3.6.7"
MINIO_VER="RELEASE.2025-10-15T17-29-55Z"
OPENSEARCH_VER="3.4.0"

# ВЕРНУЛИ ПРАВИЛЬНУЮ МОДЕЛЬ
# Вес: ~46 ГБ (4-bit AWQ). Требует 2 карты по 24GB.
MODEL_ID="cyankiwi/Qwen3-Next-80B-A3B-Instruct-AWQ-4bit"
RERANKER_ID="Qwen/Qwen3-8B-Instruct"

INSTALL_DIR="/opt/rag_stack"
DATA_DIR="/workspace/data"

mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/etcd" "$DATA_DIR/minio" "$DATA_DIR/milvus" "$DATA_DIR/hf_cache"

# 1. System Dependencies
echo "[1/8] Installing dependencies..."
apt-get update && apt-get install -y libaio-dev libaio1 wget curl python3-pip python3-venv git libnuma-dev

# 2. Clone Repo
echo "[2/8] Cloning Repository..."
if [ ! -d "/workspace/research" ]; then
    git clone -b feature/agentic-rag https://github.com/The-Yellow-Sign/research.git /workspace/research || echo "⚠️ Repo clone failed."
else
    cd /workspace/research && git pull origin feature/agentic-rag
fi

# 3. Etcd v3.6
echo "[3/8] Setting up Etcd..."
if ! pgrep etcd >/dev/null; then
    cd "$INSTALL_DIR"
    wget -qN https://github.com/etcd-io/etcd/releases/download/${ETCD_VER}/etcd-${ETCD_VER}-linux-amd64.tar.gz
    tar xzf etcd-${ETCD_VER}-linux-amd64.tar.gz
    cp etcd-${ETCD_VER}-linux-amd64/etcd /usr/local/bin/
    nohup etcd --data-dir "$DATA_DIR/etcd" --experimental-memory-limit-in-bytes 536870912 > "$INSTALL_DIR/etcd.log" 2>&1 &
fi

# 4. MinIO
echo "[4/8] Setting up MinIO..."
if ! pgrep minio >/dev/null; then
    wget -q -O /usr/local/bin/minio "https://dl.min.io/server/minio/release/linux-amd64/minio.${MINIO_VER}"
    chmod +x /usr/local/bin/minio
    export MINIO_ROOT_USER=minioadmin
    export MINIO_ROOT_PASSWORD=minioadmin
    nohup minio server "$DATA_DIR/minio" --console-address ":9001" > "$INSTALL_DIR/minio.log" 2>&1 &
fi

# 5. Milvus 2.6
echo "[5/8] Setting up Milvus..."
if ! pgrep milvus >/dev/null; then
    cd "$INSTALL_DIR"
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$INSTALL_DIR/lib
    wget -qN https://github.com/milvus-io/milvus/releases/download/v${MILVUS_VER}/milvus_${MILVUS_VER}-1_amd64.deb -O milvus.deb
    dpkg -i milvus.deb || apt-get install -f -y

    cat <<EOF > "$INSTALL_DIR/milvus.yaml"
etcd:
  endpoints: [localhost:2379]
minio:
  address: localhost
  port: 9000
  accessKeyID: minioadmin
  secretAccessKey: minioadmin
  bucketName: milvus-bucket
storage:
  path: $DATA_DIR/milvus
EOF
    nohup milvus run standalone --config "$INSTALL_DIR/milvus.yaml" > "$INSTALL_DIR/milvus.log" 2>&1 &
    sleep 5
fi

# 6. OpenSearch
echo "[6/8] Setting up OpenSearch..."
if ! curl -s localhost:9200 >/dev/null; then
    cd "$INSTALL_DIR"
    if [ ! -d "opensearch-${OPENSEARCH_VER}" ]; then
        wget -q https://artifacts.opensearch.org/releases/bundle/opensearch/${OPENSEARCH_VER}/opensearch-${OPENSEARCH_VER}-linux-x64.tar.gz
        tar xzf opensearch-${OPENSEARCH_VER}-linux-x64.tar.gz
    fi
    if ! id -u opensearch >/dev/null 2>&1; then useradd -m -s /bin/bash opensearch; fi
    chown -R opensearch:opensearch "$INSTALL_DIR/opensearch-${OPENSEARCH_VER}"
    su - opensearch -c "export OPENSEARCH_JAVA_OPTS='-Xms2g -Xmx2g'; cd $INSTALL_DIR/opensearch-${OPENSEARCH_VER} && nohup ./bin/opensearch -E 'discovery.type=single-node' -E 'network.host=0.0.0.0' > opensearch.log 2>&1 &"
    sleep 10
fi

# 7. Python & SGLang (Qwen3-Next Ready)
echo "[7/8] Installing SGLang environment..."
if ! command -v uv &> /dev/null; then curl -LsSf https://astral.sh/uv/install.sh | sh; fi
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

cd "$INSTALL_DIR"
uv venv
source .venv/bin/activate

# Ставим Torch 2.5 (обязателен для Qwen3-Next)
uv pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124

# FlashInfer для гибридной архитектуры
pip install flashinfer-python -i https://flashinfer.ai/whl/cu124/torch2.5/

# SGLang свежий
uv pip install "sglang[all]>=0.5.7" --extra-index-url https://download.pytorch.org/whl/cu124
pip install --upgrade sgl-kernel

uv pip install pymilvus opensearch-py openai huggingface_hub hf_transfer

# 8. Download Models
echo "[8/8] Downloading Models..."
export HF_HOME="$DATA_DIR/hf_cache"
export HF_HUB_ENABLE_HF_TRANSFER=1

if [ ! -z "$HF_TOKEN" ]; then
    huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential
fi

# Качаем Qwen3-Next-80B-A3B (AWQ)
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$MODEL_ID', allow_patterns=['*.safetensors', '*.json', '*.model', '*.txt'])"
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$RERANKER_ID')"

# 9. Launch Script
cat <<EOF > /root/start_sglang.sh
#!/bin/bash
source $INSTALL_DIR/.venv/bin/activate
export HF_HOME="$DATA_DIR/hf_cache"

# ВАЖНО: TP_SIZE=2 обязательно для 2x3090/4090.
# Если у вас 1x A6000/A100 (48GB+), можно ставить 1.
TP_SIZE=2 

echo "Starting Qwen3-Next-80B-A3B (AWQ)... TP=\$TP_SIZE"

# Флаги для Qwen3-Next (Hybrid Architecture):
# --enable-mixed-chunk-attention: Включает оптимизацию для гибридной DeltaNet+Attention
# --mem-fraction-static 0.85: Оставляем место под KV-кэш (он тут специфичный)

nohup python -m sglang.launch_server \\
  --model-path $MODEL_ID \\
  --host 0.0.0.0 --port 8000 \\
  --tp \$TP_SIZE \\
  --mem-fraction-static 0.80 \\
  --quantization awq \\
  --trust-remote-code \\
  --enable-mixed-chunk-attention > $INSTALL_DIR/sglang_main.log 2>&1 &

echo "Starting Reranker..."
nohup python -m sglang.launch_server \\
  --model-path $RERANKER_ID \\
  --host 0.0.0.0 --port 8001 \\
  --tp 1 \\
  --mem-fraction-static 0.10 \\
  --trust-remote-code > $INSTALL_DIR/sglang_reranker.log 2>&1 &

echo "✅ Qwen3-Next System Started!"
EOF
chmod +x /root/start_sglang.sh

echo "=========================================="
echo "✅ Setup Complete. Model: Qwen3-Next-80B-A3B"
echo "Run: /root/start_sglang.sh"
echo "=========================================="