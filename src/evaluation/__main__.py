"""Точка входа для запуска UnifiedEvaluator.

Запуск:
    python -m src.evaluation --mode agent --dataset ...
"""

import argparse
import asyncio
import logging
from pathlib import Path

from src.application.services.rag_service import RAGService
from src.application.services.tool_factory import create_default_tools
from src.application.use_cases.agent_controller import AgentController
from src.evaluation.adapters import AgentAdapter, BaseSystemAdapter, RAGAdapter
from src.evaluation.run import UnifiedEvaluator
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.search.engine import SearchEngine

logger = logging.getLogger("eval_runner")


async def main():
    """Запускает унифицированную оценку."""
    parser = argparse.ArgumentParser(description="Unified RAG/Agent Evaluator")
    parser.add_argument("--mode", choices=["rag", "agent"], required=True)
    parser.add_argument("--dataset", type=Path, required=True, help="Path to golden dataset")
    parser.add_argument("--output", type=Path, default=Path("reports"), help="Output directory")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--sample", type=int, help="Run only N samples")
    parser.add_argument("--no-ragas", action="store_true", help="Disable RAGAS evaluation")

    args = parser.parse_args()

    adapter: BaseSystemAdapter

    if args.mode == "rag":
        logger.info("Initializing RAG Adapter...")
        search_engine = SearchEngine()
        llm_client = LLMClient()

        rag_service = RAGService(search_engine=search_engine, llm_client=llm_client)
        adapter = RAGAdapter(rag_service)

    elif args.mode == "agent":
        logger.info("Initializing Agent Adapter...")
        search_engine = SearchEngine()
        llm_client = LLMClient()

        tools = create_default_tools(search_engine=search_engine, llm_client=llm_client)

        controller = AgentController(llm=llm_client, tools=tools)
        adapter = AgentAdapter(controller)

    evaluator = UnifiedEvaluator(
        adapter=adapter, output_dir=args.output, resume=args.resume, ragas_enabled=not args.no_ragas
    )

    await evaluator.evaluate_dataset(args.dataset, args.sample)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("\nEvaluation interrupted by user.")
    except Exception as e:
        logger.exception("Fatal error during evaluation: %s", e)
