"""Kingdom AI Agents — CLI entry point.

Usage:
    python main.py web-export --url "https://example.com/data-page"
    python main.py web-export --url "https://example.com/data-page" --output "my_data.json"
    python main.py json-transform --input-dir "./my-data-folder"
    python main.py image-select --input "./slides.json"
    python main.py image-mask --url "https://example.com/photo.jpg"
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


def run_json_transform(args: argparse.Namespace) -> None:
    """Run the JSON Schema Transformer agent."""
    from infrastructure.llm.gemini_provider import GeminiProvider
    from infrastructure.executor.subprocess_executor import SubprocessExecutor
    from agents.json_schema_transformer.agent import JsonSchemaTransformerAgent
    from agents.json_schema_transformer.models import TransformConfig

    # Create provider and executor
    llm_provider = GeminiProvider()
    script_executor = SubprocessExecutor()

    # Create agent
    agent = JsonSchemaTransformerAgent(
        llm_provider=llm_provider,
        script_executor=script_executor,
        workspace_dir=WORKSPACE_DIR,
    )

    # Create config
    config = TransformConfig(
        input_dir=Path(args.input_dir).resolve(),
    )

    # Run the pipeline
    try:
        result = agent.run(config)
        print(f"\n🎉 Success! Transformed {result.record_count} records.")
        print(f"📄 Output: {result.json_path}")
        print(f"📊 Columns: {', '.join(result.columns)}")
        if result.errors:
            print(f"⚠️  Warnings: {'; '.join(result.errors)}")
    except Exception as e:
        logging.getLogger(__name__).error(f"Transform failed: {e}", exc_info=True)
        print(f"\n❌ Transform failed: {e}", file=sys.stderr)
        sys.exit(1)


def run_image_select(args: argparse.Namespace) -> None:
    """Run the Image Selector agent."""
    from agents.image_selector.agent import ImageSelectorAgent
    from agents.image_selector.models import SelectorConfig

    # Determine output path
    if args.output:
        output_path = Path(args.output).resolve()
    else:
        output_path = OUTPUT_DIR / "selections.json"

    # Create agent
    agent = ImageSelectorAgent(
        workspace_dir=WORKSPACE_DIR,
        output_dir=OUTPUT_DIR,
    )

    # Create config
    config = SelectorConfig(
        input_path=Path(args.input).resolve(),
        output_path=output_path,
    )

    # Run the pipeline
    try:
        result = agent.run(config)
        print(f"\n🎉 Done! Selected {len(result.selections)} images across {result.total_slides} slides.")
        print(f"📄 Output: {result.output_path}")
        if result.skipped_slides:
            print(f"⏭️  Skipped slides: {result.skipped_slides}")
    except Exception as e:
        logging.getLogger(__name__).error(f"Image selection failed: {e}", exc_info=True)
        print(f"\n❌ Image selection failed: {e}", file=sys.stderr)
        sys.exit(1)


def run_image_mask(args: argparse.Namespace) -> None:
    """Run the Image Masker agent (interactive terminal multi-select for strategies)."""
    from core.ui.terminal_select import TerminalSelectCancelled

    from agents.image_masker.agent import ImageMaskerAgent
    from agents.image_masker.models import MaskerConfig

    output_path = Path(args.output).resolve() if args.output else None

    agent = ImageMaskerAgent(output_dir=OUTPUT_DIR)
    config = MaskerConfig(
        image_url=args.url,
        output_path=output_path,
    )

    try:
        result = agent.run(config)
    except TerminalSelectCancelled:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logging.getLogger(__name__).error(f"Image mask failed: {e}", exc_info=True)
        print(f"\n❌ Image mask failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n🎉 Saved masked image.")
    print(f"📄 Output: {result.output_path}")
    if result.applied_strategies:
        names = ", ".join(s.value for s in result.applied_strategies)
        print(f"🧩 Applied: {names}")
    else:
        print("🧩 No strategies selected — saved a PNG copy of the RGB image.")


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

    # JSON Schema Transformer agent
    json_transform_parser = subparsers.add_parser(
        "json-transform",
        help="Transform raw JSON data to match a target schema.",
        description=(
            "Reads raw-data.json and schema.json from the input directory, "
            "uses an LLM to analyze the transformation requirements, "
            "generates a Python script, and produces output.json in the same directory."
        ),
    )
    json_transform_parser.add_argument(
        "--input-dir",
        required=True,
        help="Path to the directory containing raw-data.json and schema.json.",
    )
    json_transform_parser.set_defaults(func=run_json_transform)

    # Image Selector agent
    image_select_parser = subparsers.add_parser(
        "image-select",
        help="Select images from slides via a GUI.",
        description=(
            "Presents images in a slide-based GUI. The user selects one image "
            "per slide (or skips). Outputs a JSON file with the selections."
        ),
    )
    image_select_parser.add_argument(
        "--input",
        required=True,
        help="Path to the input JSON file with slides and images.",
    )
    image_select_parser.add_argument(
        "--output",
        default=None,
        help="Output JSON filename (defaults to output/selections.json).",
    )
    image_select_parser.set_defaults(func=run_image_select)

    # Image Masker agent
    image_mask_parser = subparsers.add_parser(
        "image-mask",
        help="Apply masking transforms to an image to differentiate it from the original.",
        description=(
            "Downloads an image from a URL, presents an interactive terminal \n"
            "multi-select for choosing masking strategies (flip, color shift, \n"
            "zoom, rotation, noise, etc.), applies them, and saves the result."
        ),
    )
    image_mask_parser.add_argument(
        "--url",
        required=True,
        help="URL of the source image to mask.",
    )
    image_mask_parser.add_argument(
        "--output",
        default=None,
        help="Output image path (auto-derived from URL if omitted).",
    )
    image_mask_parser.set_defaults(func=run_image_mask)

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
