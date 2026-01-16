#!/bin/bash
set -e


# ==========================================
# Vast.ai On-Start Script
# Installs: Etcd, MinIO, Milvus (Standalone), SGLang
# Downloads: Qwen/Qwen3-80B-Instruct-FP8
# ==========================================

# Configuration
MILVUS_VER="2.4.0"
ETCD_VER="v3.5.11"
MINIO_VER="RELEASE.2024-01-16T16-07-38Z"
MODEL_ID="Qwen/Qwen3-Next-80B-A3B-Instruct-FP8"
RERANKER_ID="Qwen/Qwen3-8B-FP8"
INSTALL_DIR="/opt/rag_stack"
DATA_DIR="/workspace/data" # Persisted volume on Vast.ai

mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR"
mkdir -p "$DATA_DIR/etcd" "$DATA_DIR/minio" "$DATA_DIR/milvus" "$DATA_DIR/hf_cache"

# 1. System Dependencies
echo "[1/8] Installing system dependencies..."
apt-get update && apt-get install -y libaio-dev libaio1 wget curl python3-pip python3-venv git libnuma-dev

# 2. Clone Repository
echo "[2/8] Cloning Repository..."
if [ ! -d "/workspace/research" ]; then
    # Try public clone first
    git clone -b feature/agentic-rag https://github.com/The-Yellow-Sign/research.git /workspace/research || echo "⚠️ Repository clone failed (might be private). Clone manually."
else
    echo "Repository already exists in /workspace/research"
    cd /workspace/research && git pull origin feature/agentic-rag
fi

# 2. Install & Start Etcd
echo "[2/7] Setting up Etcd..."
if ! pgrep etcd >/dev/null; then
    cd "$INSTALL_DIR"
    if [ ! -f "etcd-${ETCD_VER}-linux-amd64.tar.gz" ]; then
        wget -q https://github.com/etcd-io/etcd/releases/download/${ETCD_VER}/etcd-${ETCD_VER}-linux-amd64.tar.gz
    fi
    tar xzf etcd-${ETCD_VER}-linux-amd64.tar.gz
    cp etcd-${ETCD_VER}-linux-amd64/etcd /usr/local/bin/
    
    nohup etcd --data-dir "$DATA_DIR/etcd" > "$INSTALL_DIR/etcd.log" 2>&1 &
    sleep 2
    echo "✅ Etcd started."
else
    echo "Etcd already running."
fi

# 3. Install & Start MinIO
echo "[3/7] Setting up MinIO..."
if ! pgrep minio >/dev/null; then
    if [ ! -f "/usr/local/bin/minio" ]; then
        wget -q -O /usr/local/bin/minio https://dl.min.io/server/minio/release/linux-amd64/minio
        chmod +x /usr/local/bin/minio
    fi
    
    export MINIO_ROOT_USER=minioadmin
    export MINIO_ROOT_PASSWORD=minioadmin
    nohup minio server "$DATA_DIR/minio" --console-address ":9001" > "$INSTALL_DIR/minio.log" 2>&1 &
    sleep 2
    echo "✅ MinIO started."
else
    echo "MinIO already running."
fi

# 4. Install & Start Milvus (Standalone)
echo "[4/7] Setting up Milvus Standalone..."
# Note: Installing Milvus binary directly is tricky. Using a pre-built binary if available or docker is better.
# Assuming user wants binary execution.
if ! pgrep milvus >/dev/null; then
    cd "$INSTALL_DIR"
    # Milvus standalone usually requires library paths
    export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$INSTALL_DIR/lib
    
    # Download Milvus Binary (using a known stable release asset or generic method if .deb fails)
    # Trying the .deb approach as requested, but adding fallback
    wget -q https://github.com/milvus-io/milvus/releases/download/v${MILVUS_VER}/milvus_${MILVUS_VER}-1_amd64.deb -O milvus.deb
    dpkg -i milvus.deb || apt-get install -f -y
    
    # Run Milvus Standalone
    # Using 'embedded' or 'standalone' mode requires proper config
    cat <<EOF > "$INSTALL_DIR/milvus.yaml"
etcd:
  endpoints:
    - localhost:2379
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
    echo "✅ Milvus started."
else
    echo "Milvus already running."
fi

# 5. Install & Start OpenSearch
echo "[5/8] Setting up OpenSearch..."
if ! curl -s localhost:9200 >/dev/null; then
    cd "$INSTALL_DIR"
    if [ ! -d "opensearch-2.11.1" ]; then
        if [ ! -f "opensearch-2.11.1-linux-x64.tar.gz" ]; then
            wget -q https://artifacts.opensearch.org/releases/bundle/opensearch/2.11.1/opensearch-2.11.1-linux-x64.tar.gz
        fi
        tar xzf opensearch-2.11.1-linux-x64.tar.gz
    fi
    
    # Configure generic user execution (since running as root in docker is common on vast)
    # OpenSearch usually complains about running as root. 
    # We can use OPENSEARCH_JAVA_OPTS to define environment
    export OPENSEARCH_JAVA_OPTS="-Xms1g -Xmx1g"
    
    # Need to run as non-root usually, or force it. 
    # Creating a user for opensearch
    if ! id -u opensearch >/dev/null 2>&1; then
        useradd -m -s /bin/bash opensearch
    fi
    chown -R opensearch:opensearch "$INSTALL_DIR/opensearch-2.11.1"
    
    # Run in background
    su - opensearch -c "cd $INSTALL_DIR/opensearch-2.11.1 && nohup ./bin/opensearch -E 'discovery.type=single-node' -E 'network.host=0.0.0.0' > opensearch.log 2>&1 &"
    
    sleep 15
    echo "✅ OpenSearch started."
else
    echo "OpenSearch already running."
fi

# 6. Install Python & SGLang
echo "[6/8] Installing SGLang environment..."
# Install uv
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Ensure uv is in PATH (it installs to ~/.local/bin usually)
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

cd "$INSTALL_DIR"
uv venv
source .venv/bin/activate

# FIX: Install torch FIRST so flashinfer has build dependencies
uv pip install torch --index-url https://download.pytorch.org/whl/cu121

# FIX: Manually install specific version of flashinfer-python via pip
# This avoids uv's strict resolver issues with missing metadata in the index
pip install flashinfer-python==0.2.13

echo "Installing SGLang..."
# Use unsafe-best-match to resolve setuptools/packaging conflicts between PyPI and PyTorch indices
uv pip install "sglang[all]" --extra-index-url https://download.pytorch.org/whl/cu121 --index-strategy unsafe-best-match

uv pip install pymilvus opensearch-py openai huggingface_hub

# 7. Download Models
echo "[7/8] Downloading Models..."
export HF_HOME="$DATA_DIR/hf_cache"

if [ -z "$HF_TOKEN" ]; then
    echo "⚠️  HF_TOKEN not set. Make sure it's in env vars or exported at top of script."
else
    huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential
fi

# Use hf_transfer for speed
uv pip install hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=1

python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$MODEL_ID', allow_patterns=['*.safetensors', '*.json', '*.model', '*.txt'])"
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$RERANKER_ID')"

# 8. Create Launch Script
cat <<EOF > /root/start_sglang.sh
#!/bin/bash
source $INSTALL_DIR/.venv/bin/activate
export HF_HOME="$DATA_DIR/hf_cache"

echo "Starting SGLang Main ($MODEL_ID)..."
nohup python -m sglang.launch_server \\
  --model-path $MODEL_ID \\
  --host 0.0.0.0 --port 8000 \\
  --tp 1 --mem-fraction-static 0.85 \\
  --trust-remote-code > $INSTALL_DIR/sglang_main.log 2>&1 &

echo "Starting SGLang Reranker ($RERANKER_ID)..."
nohup python -m sglang.launch_server \\
  --model-path $RERANKER_ID \\
  --host 0.0.0.0 --port 8001 \\
  --mem-fraction-static 0.10 \\
  --trust-remote-code > $INSTALL_DIR/sglang_reranker.log 2>&1 &

echo "SGLang services starting in background. Check logs in $INSTALL_DIR/"
EOF
chmod +x /root/start_sglang.sh

echo "=========================================="
echo "✅ Setup Complete!"
echo "------------------------------------------"
echo "Start SGLang:  /root/start_sglang.sh"
echo "Milvus Port: 19530"
echo "MinIO Console: 9001 (User/Pass: minioadmin)"
echo "OpenSearch: 9200"
echo "Models: $DATA_DIR/hf_cache"
echo "=========================================="
