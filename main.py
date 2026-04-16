"""Kingdom AI Agents — CLI entry point.

Usage:
    python main.py web-export --url "https://example.com/data-page"
    python main.py web-export --url "https://example.com/data-page" --output "my_data.json"
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv


# Project root directory
PROJECT_ROOT = Path(__file__).parent
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
OUTPUT_DIR = PROJECT_ROOT / "output"


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the application."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def run_web_export(args: argparse.Namespace) -> None:
    """Run the Web Data Exporter agent."""
    # Late imports to keep CLI fast and allow dependency injection
    from infrastructure.llm.gemini_provider import GeminiProvider
    from infrastructure.executor.subprocess_executor import SubprocessExecutor
    from agents.web_data_exporter.agent import WebDataExporterAgent
    from agents.web_data_exporter.models import ExportConfig

    # Create provider and executor
    llm_provider = GeminiProvider()
    script_executor = SubprocessExecutor()

    # Create agent
    agent = WebDataExporterAgent(
        llm_provider=llm_provider,
        script_executor=script_executor,
        workspace_dir=WORKSPACE_DIR,
        output_dir=OUTPUT_DIR,
    )

    # Create config
    config = ExportConfig(
        url=args.url,
        output_filename=args.output,
    )

    # Run the pipeline
    try:
        result = agent.run(config)
        print(f"\n🎉 Success! Exported {result.record_count} records.")
        print(f"📄 Output: {result.json_path}")
        print(f"📊 Columns: {', '.join(result.columns)}")
        if result.errors:
            print(f"⚠️  Warnings: {'; '.join(result.errors)}")
    except Exception as e:
        logging.getLogger(__name__).error(f"Export failed: {e}", exc_info=True)
        print(f"\n❌ Export failed: {e}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="kingdom-ai-agents",
        description="Kingdom AI Agents — A collection of AI-powered automation agents.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging.",
    )

    subparsers = parser.add_subparsers(
        title="agents",
        description="Available agents",
        dest="agent",
    )

    # Web Data Exporter agent
    web_export_parser = subparsers.add_parser(
        "web-export",
        help="Export structured data from a web page to JSON.",
        description=(
            "Downloads a web page, analyzes its structure using an LLM, "
            "generates an extraction script, and exports the data to JSON."
        ),
    )
    web_export_parser.add_argument(
        "--url",
        required=True,
        help="URL of the web page to export data from.",
    )
    web_export_parser.add_argument(
        "--output",
        default=None,
        help="Output JSON filename (auto-derived from URL if omitted).",
    )
    web_export_parser.set_defaults(func=run_web_export)

    return parser


def main() -> None:
    """Main entry point."""
    # Load environment variables from .env file
    load_dotenv(PROJECT_ROOT / ".env")

    parser = build_parser()
    args = parser.parse_args()

    if not args.agent:
        parser.print_help()
        sys.exit(0)

    setup_logging(verbose=args.verbose)
    args.func(args)


if __name__ == "__main__":
    main()
