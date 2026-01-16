#!/bin/bash
set -e

# ==========================================
# Vast.ai On-Start Script for RAG Stack
# Uses: vLLM + Milvus Lite + OpenSearch + uv
# Hardware: 1x H100 80GB (or 80GB+ GPU)
# ==========================================

MODEL_ID="cyankiwi/Qwen3-Next-80B-A3B-Instruct-AWQ-4bit"
RERANKER_ID="Qwen/Qwen3-8B-FP8"
INSTALL_DIR="/opt/rag_stack"
DATA_DIR="/workspace/data"
OPENSEARCH_VER="2.11.1"

mkdir -p "$INSTALL_DIR" "$DATA_DIR" "$DATA_DIR/hf_cache"

# ====================
# 1. System Dependencies + uv
# ====================
echo "[1/6] Installing system dependencies..."
apt-get update && apt-get install -y openjdk-17-jre-headless git curl wget

echo "[1.5/6] Installing uv and Python 3.13..."
if ! command -v /root/.local/bin/uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# Install Python 3.13
uv python install 3.13

# ====================
# 2. Clone Repository
# ====================
echo "[2/6] Cloning Repository..."
if [ ! -d "/workspace/research" ]; then
    git clone -b feature/agentic-rag https://github.com/The-Yellow-Sign/research.git /workspace/research || true
else
    cd /workspace/research && git pull origin feature/agentic-rag || true
fi

# ====================
# 3. OpenSearch (для BM25)
# ====================
echo "[3/6] Setting up OpenSearch..."
if ! curl -s localhost:9200 >/dev/null 2>&1; then
    cd "$INSTALL_DIR"
    
    if [ ! -d "opensearch-${OPENSEARCH_VER}" ]; then
        curl -L -o opensearch.tar.gz \
            "https://artifacts.opensearch.org/releases/bundle/opensearch/${OPENSEARCH_VER}/opensearch-${OPENSEARCH_VER}-linux-x64.tar.gz"
        tar xzf opensearch.tar.gz && rm opensearch.tar.gz
    fi
    
    # Disable security
    grep -q "plugins.security.disabled" "opensearch-${OPENSEARCH_VER}/config/opensearch.yml" || \
        echo "plugins.security.disabled: true" >> "opensearch-${OPENSEARCH_VER}/config/opensearch.yml"
    
    # Create user
    id -u opensearch >/dev/null 2>&1 || useradd -m -s /bin/bash opensearch
    chown -R opensearch:opensearch "opensearch-${OPENSEARCH_VER}"
    
    # Start
    su - opensearch -c "
        export OPENSEARCH_JAVA_OPTS='-Xms2g -Xmx2g'
        cd $INSTALL_DIR/opensearch-${OPENSEARCH_VER}
        nohup ./bin/opensearch -E 'discovery.type=single-node' \
            -E 'network.host=0.0.0.0' \
            -E 'node.store.allow_mmap=false' > logs/opensearch.log 2>&1 &
    "
    sleep 10
fi
echo "  ✓ OpenSearch: $(curl -s localhost:9200 >/dev/null && echo 'RUNNING' || echo 'STARTING...')"

# ====================
# 4. Python Dependencies via uv
# ====================
echo "[4/6] Installing Python dependencies via uv..."
cd /workspace/research
uv sync

# ====================
# 5. Download Models
# ====================
echo "[5/6] Downloading Models..."
export HF_HOME="$DATA_DIR/hf_cache"
export HF_HUB_ENABLE_HF_TRANSFER=1

if [ -n "$HF_TOKEN" ]; then
    huggingface-cli login --token "$HF_TOKEN" --add-to-git-credential
fi

python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$MODEL_ID', allow_patterns=['*.safetensors', '*.json', '*.model', '*.txt'])"
python3 -c "from huggingface_hub import snapshot_download; snapshot_download('$RERANKER_ID')"

# ====================
# 6. Fix libcuda.so for vLLM
# ====================
echo "[6/6] Fixing CUDA library paths..."
echo "/usr/lib/x86_64-linux-gnu" > /etc/ld.so.conf.d/cuda-local.conf
ldconfig

# ====================
# Create Launch Scripts
# ====================
cat > /root/start_vllm.sh <<'EOF'
#!/bin/bash
export HF_HOME="/workspace/data/hf_cache"

# Fix libcuda.so for linker (needed for vLLM JIT compilation)
echo "/usr/lib/x86_64-linux-gnu" > /etc/ld.so.conf.d/cuda-local.conf
ldconfig

echo "Starting vLLM with Qwen3-Next-80B-A3B (AWQ)..."

# Main LLM (port 8000) with --enforce-eager to avoid CUDA graph issues
nohup python3 -m vllm.entrypoints.openai.api_server \
  --model cyankiwi/Qwen3-Next-80B-A3B-Instruct-AWQ-4bit \
  --tensor-parallel-size 1 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --enforce-eager \
  --host 0.0.0.0 --port 8000 \
  > /tmp/vllm_main.log 2>&1 &

echo "Waiting 90s for Main LLM to load..."
sleep 90

echo "Starting LLM Reranker on port 8001..."

# LLM Reranker (port 8001) — for LLM-based reranking
nohup python3 -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-8B-FP8 \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.10 \
  --max-model-len 4096 \
  --enforce-eager \
  --host 0.0.0.0 --port 8001 \
  > /tmp/vllm_reranker.log 2>&1 &

echo "✅ vLLM Started!"
echo "Main LLM: http://localhost:8000/v1"
echo "Reranker: http://localhost:8001/v1"
echo "Logs: /tmp/vllm_main.log, /tmp/vllm_reranker.log"
EOF
chmod +x /root/start_vllm.sh

# Create ingestion script
cat > /root/run_ingestion.sh <<'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
export LLM_BASE_URL="http://localhost:8000/v1"
export LLM_MODEL="cyankiwi/Qwen3-Next-80B-A3B-Instruct-AWQ-4bit"
export OPENSEARCH_HOST="localhost"
export OPENSEARCH_PORT="9200"
export HF_HOME="/workspace/data/hf_cache"

cd /workspace/research
uv run python -m src.interfaces.cli ingest --source devops-playbooks --clear
EOF
chmod +x /root/run_ingestion.sh

# Create evaluation script
cat > /root/run_evaluation.sh <<'EOF'
#!/bin/bash
export PATH="$HOME/.local/bin:$PATH"
export LLM_BASE_URL="http://localhost:8000/v1"
export LLM_MODEL="cyankiwi/Qwen3-Next-80B-A3B-Instruct-AWQ-4bit"
export RERANKER_URL="http://localhost:8001/v1"
export OPENSEARCH_HOST="localhost"
export OPENSEARCH_PORT="9200"
export HF_HOME="/workspace/data/hf_cache"

cd /workspace/research
uv run python -m src.evaluation.run_evaluation "$@"
EOF
chmod +x /root/run_evaluation.sh

echo "=========================================="
echo "✅ Setup Complete!"
echo ""
echo "📦 Components:"
echo "  • Vector DB: Milvus Lite (embedded)"
echo "  • BM25: OpenSearch at localhost:9200"
echo "  • Python: 3.13 via uv"
echo ""
echo "🚀 Next Steps:"
echo "  1. /root/start_vllm.sh      - Start LLM + Reranker"
echo "  2. /root/run_ingestion.sh   - Index documents"
echo "  3. /root/run_evaluation.sh  - Run RAG evaluation"
echo "=========================================="