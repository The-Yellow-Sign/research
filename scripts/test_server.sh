#!/usr/bin/env bash
# scripts/test_server.sh — Полный тест RAG с локальными моделями (SGLang)
# Запуск: ./scripts/test_server.sh

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="${RAG_API_URL:-http://localhost:8080}"
SGLANG_URL="http://localhost:8000"

echo "=========================================="
echo "🚀 RAG Full Integration Test (Local Models)"
echo "=========================================="
echo ""

echo -e "${BLUE}[1/7] Запуск инфраструктуры и SGLang...${NC}"
docker compose up -d milvus opensearch
docker compose --profile gpu up -d sglang-main sglang-reranker 2>/dev/null || echo -e "${YELLOW}⚠️  SGLang не запущен (нет GPU?)${NC}"

echo "Ожидание готовности..."

for i in {1..30}; do
    if curl -sf http://localhost:9091/healthz >/dev/null 2>&1; then
        echo -e "${GREEN}✅ Milvus готов${NC}"
        break
    fi
    [ $i -eq 30 ] && echo -e "${RED}❌ Milvus не отвечает${NC}" && exit 1
    sleep 2
done

for i in {1..30}; do
    if curl -sf http://localhost:9200 >/dev/null 2>&1; then
        echo -e "${GREEN}✅ OpenSearch готов${NC}"
        break
    fi
    [ $i -eq 30 ] && echo -e "${RED}❌ OpenSearch не отвечает${NC}" && exit 1
    sleep 2
done
echo ""

echo -e "${BLUE}[2/7] Проверка SGLang...${NC}"
SGLANG_READY=false
for i in {1..100}; do
    if curl -sf "${SGLANG_URL}/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ SGLang готов (${SGLANG_URL})${NC}"
        SGLANG_READY=true
        break
    fi
    [ $i -eq 100 ] && echo -e "${YELLOW}⚠️  SGLang не готов, используем OpenRouter${NC}"
    sleep 3
done

if [ "$SGLANG_READY" = true ]; then
    echo -e "${GREEN}→ Используем локальные модели (SGLang)${NC}"
    export LLM_BASE_URL="${SGLANG_URL}/v1"
    export LLM_MODEL="Qwen/Qwen3-80B-Instruct-FP8"
else
    echo -e "${YELLOW}→ Используем OpenRouter (удалённые модели)${NC}"
fi
echo ""

echo -e "${BLUE}[3/7] Индексация документов...${NC}"
uv run python -m src.interfaces.cli.commands.ingest
echo -e "${GREEN}✅ Индексация завершена${NC}"
echo ""
echo -e "${BLUE}[4/7] Запуск RAG API...${NC}"
uv run python -m src.interfaces.api.app &
API_PID=$!
trap "kill $API_PID 2>/dev/null; echo 'API остановлен'" EXIT

for i in {1..30}; do
    if curl -sf "${API_URL}/health" >/dev/null 2>&1; then
        echo -e "${GREEN}✅ RAG API готов (${API_URL})${NC}"
        break
    fi
    [ $i -eq 30 ] && echo -e "${RED}❌ RAG API не запустился${NC}" && exit 1
    sleep 2
done
echo ""

echo -e "${BLUE}[5/7] Проверка готовности сервисов...${NC}"
curl -sf "${API_URL}/health/ready" | python3 -m json.tool 2>/dev/null || echo "Не удалось получить статус"
echo ""
echo -e "${BLUE}[6/7] Тестовый запрос к RAG...${NC}"
RESPONSE=$(curl -sf -X POST "${API_URL}/chat" \
    -H "Content-Type: application/json" \
    -d '{"query": "Как настроить nginx reverse proxy?"}' 2>/dev/null || echo '{"error": "no response"}')

if echo "$RESPONSE" | grep -q '"answer"'; then
    echo -e "${GREEN}✅ RAG ответил успешно${NC}"
    echo "$RESPONSE" | python3 -c "import sys,json; r=json.load(sys.stdin); print('Ответ:', r.get('answer','')[:200]+'...')" 2>/dev/null || true
else
    echo -e "${RED}❌ Ошибка RAG${NC}"
    echo "$RESPONSE"
fi
echo ""
echo -e "${BLUE}[7/7] Запуск Evaluation (sample=5)...${NC}"
echo "Это займёт несколько минут..."
uv run python -m src.evaluation.run_evaluation --sample 5 --output-dir volumes/evaluation/test_run

echo ""
echo "=========================================="
echo -e "${GREEN}🎉 Все тесты завершены!${NC}"
echo "Отчёт: volumes/evaluation/test_run/"
echo "=========================================="
