"""JSON Schema Transformer Agent — Main pipeline orchestrator."""

import json
import logging
import textwrap
from pathlib import Path

from core.executor.base import ScriptExecutor, ScriptExecutionError
from core.llm.base import LLMProvider, LLMProviderError
from core.llm.models import LLMRequest

from agents.json_schema_transformer.models import (
    FieldMapping,
    TransformAnalysis,
    TransformConfig,
    TransformResult,
)
from agents.json_schema_transformer.prompts import (
    ANALYSIS_SYSTEM_INSTRUCTION,
    SCRIPT_GENERATION_SYSTEM_INSTRUCTION,
    build_analysis_prompt,
    build_script_generation_prompt,
)

logger = logging.getLogger(__name__)


class JsonSchemaTransformerAgent:
    """Agent that transforms raw JSON data into a new JSON file following a schema.

    Pipeline:
        1. Load raw-data.json and schema.json from the input directory
        2. Analyze the transformation requirements with LLM
        3. Generate a Python transformation script with LLM
        4. Execute the generated script
        5. Validate the output JSON
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        script_executor: ScriptExecutor,
        workspace_dir: Path,
    ):
        """Initialize the agent.

        Args:
            llm_provider: LLM provider for analysis and code generation.
            script_executor: Executor for running generated scripts.
            workspace_dir: Temporary workspace for generated scripts.
        """
        self._llm = llm_provider
        self._executor = script_executor
        self._workspace_dir = workspace_dir

        # Ensure workspace exists
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

    def run(self, config: TransformConfig) -> TransformResult:
        """Run the full transformation pipeline.

        Args:
            config: Transformation configuration (input directory).

        Returns:
            TransformResult with the path to the output JSON and metadata.

        Raises:
            Various exceptions if any step fails.
        """
        logger.info(f"{'=' * 60}")
        logger.info("JSON Schema Transformer Agent")
        logger.info(f"Input directory: {config.input_dir}")
        logger.info(f"{'=' * 60}")

        # Step 0: Validate inputs
        config.validate()

        # Step 1: Load input files
        logger.info("\n📂 Step 1: Loading input files...")
        raw_data_content = config.raw_data_path.read_text(encoding="utf-8")
        schema_content = config.schema_path.read_text(encoding="utf-8")
        logger.info(f"   raw-data.json: {len(raw_data_content):,} characters")
        logger.info(f"   schema.json: {len(schema_content):,} characters")

        # Step 2: Analyze transformation requirements
        logger.info("\n🔍 Step 2: Analyzing transformation requirements...")
        analysis = self._analyze_transformation(raw_data_content, schema_content)
        logger.info(f"   Field mappings: {len(analysis.field_mappings)}")
        for mapping in analysis.field_mappings:
            logger.info(
                f"     • {mapping.target_field} ← "
                f"{', '.join(mapping.source_fields)} "
                f"({mapping.transformation})"
            )
        if analysis.sorting:
            logger.info(f"   Sorting: {analysis.sorting}")
        if analysis.notes:
            logger.info(f"   Notes: {analysis.notes}")

        # Steps 3+4: Generate and execute (with retry on failure)
        max_attempts = 3
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                # Step 3: Generate transformation script
                logger.info(f"\n🛠️  Step 3: Generating transformation script (attempt {attempt}/{max_attempts})...")
                script_path = self._generate_script(
                    raw_data_content, schema_content, analysis
                )
                logger.info(f"   Script saved to: {script_path.name}")

                # Step 4: Execute the script
                logger.info(f"\n⚡ Step 4: Executing transformation script (attempt {attempt}/{max_attempts})...")
                self._execute_script(
                    script_path, config.raw_data_path, config.schema_path, config.output_path
                )
                break  # Success — exit retry loop

            except (RuntimeError, ScriptExecutionError) as exc:
                last_error = exc
                if attempt < max_attempts:
                    logger.warning(
                        f"   Attempt {attempt} failed: {exc}. "
                        f"Retrying script generation..."
                    )
                else:
                    logger.error(f"   All {max_attempts} attempts failed.")
                    raise

        # Step 5: Validate and return result
        logger.info("\n✅ Step 5: Validating output...")
        result = self._validate_output(config.output_path)
        logger.info(f"   Records transformed: {result.record_count}")
        logger.info(f"   Output columns: {', '.join(result.columns)}")
        logger.info(f"   Output file: {result.json_path}")
        logger.info(f"\n{'=' * 60}")
        logger.info("Transformation complete!")
        logger.info(f"{'=' * 60}")

        return result

    def _analyze_transformation(
        self, raw_data_content: str, schema_content: str
    ) -> TransformAnalysis:
        """Step 2: Use LLM to analyze the transformation requirements."""
        request = LLMRequest(
            prompt=build_analysis_prompt(raw_data_content, schema_content),
            system_instruction=ANALYSIS_SYSTEM_INSTRUCTION,
        )

        try:
            response = self._llm.generate(request)
        except LLMProviderError as e:
            logger.error(f"LLM analysis failed: {e}")
            raise

        return self._parse_analysis_response(response.text)

    @staticmethod
    def _extract_fenced_content(text: str) -> str:
        """Extract content from between markdown code fences.

        Handles responses like:
            ```json
            { ... }
            ```
            Some extra commentary here...

        Returns the content between the fences, or the original
        text stripped if no fences are found.
        """
        stripped = text.strip()
        if not stripped.startswith("```"):
            return stripped

        lines = stripped.split("\n")
        # Drop the opening fence line (e.g. ```json)
        lines = lines[1:]

        # Find the *last* closing fence
        end_idx = None
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].strip() == "```":
                end_idx = i
                break

        if end_idx is not None:
            lines = lines[:end_idx]

        content = "\n".join(lines)
        # Strip common leading whitespace — the LLM sometimes
        # generates code inside an indented block.
        return textwrap.dedent(content)

    def _parse_analysis_response(self, response_text: str) -> TransformAnalysis:
        """Parse the LLM's JSON response into a TransformAnalysis."""
        cleaned = self._extract_fenced_content(response_text)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM analysis response as JSON: {e}")
            logger.debug(f"Raw response:\n{response_text[:1000]}")
            raise ValueError(
                f"LLM returned invalid JSON for analysis. "
                f"Response: {response_text[:200]}..."
            ) from e

        # Parse field mappings
        field_mappings = []
        for mapping_data in data.get("field_mappings", []):
            field_mappings.append(
                FieldMapping(
                    target_field=mapping_data.get("target_field", ""),
                    source_fields=mapping_data.get("source_fields", []),
                    transformation=mapping_data.get("transformation", "copy"),
                    description=mapping_data.get("description", ""),
                )
            )

        return TransformAnalysis(
            field_mappings=field_mappings,
            sorting=data.get("sorting", ""),
            notes=data.get("notes", ""),
        )

    def _generate_script(
        self,
        raw_data_content: str,
        schema_content: str,
        analysis: TransformAnalysis,
    ) -> Path:
        """Step 3: Use LLM to generate a Python transformation script."""
        # Convert field mappings to dicts for the prompt
        mappings_dicts = [
            {
                "target_field": m.target_field,
                "source_fields": m.source_fields,
                "transformation": m.transformation,
                "description": m.description,
            }
            for m in analysis.field_mappings
        ]

        request = LLMRequest(
            prompt=build_script_generation_prompt(
                raw_data_content=raw_data_content,
                schema_content=schema_content,
                analysis_field_mappings=mappings_dicts,
                analysis_sorting=analysis.sorting,
                analysis_notes=analysis.notes,
            ),
            system_instruction=SCRIPT_GENERATION_SYSTEM_INSTRUCTION,
            model="gemini-3-flash-preview",
        )

        try:
            response = self._llm.generate(request)
        except LLMProviderError as e:
            logger.error(f"LLM script generation failed: {e}")
            raise

        # Clean up the response — remove code fences if present
        script_code = self._extract_fenced_content(response.text)

        # Save the script to workspace
        script_path = self._workspace_dir / "transform_data.py"
        script_path.write_text(script_code, encoding="utf-8")

        logger.debug(
            f"Generated script ({len(script_code)} chars):\n{script_code[:500]}..."
        )

        return script_path

    def _execute_script(
        self,
        script_path: Path,
        raw_data_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> str:
        """Step 4: Execute the generated transformation script."""
        try:
            result = self._executor.execute(
                script_path=script_path,
                args=[str(raw_data_path), str(schema_path), str(output_path)],
                timeout_seconds=60,
            )
        except ScriptExecutionError as e:
            logger.error(f"Script execution failed: {e}")
            raise

        if result.stdout:
            logger.info(f"   Script output: {result.stdout.strip()}")

        if not result.success:
            error_msg = (
                f"Transformation script failed with return code {result.return_code}.\n"
                f"stderr: {result.stderr[:1000]}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        return result.stdout

    def _validate_output(self, json_path: Path) -> TransformResult:
        """Step 5: Validate the output JSON and return the result."""
        if not json_path.exists():
            raise FileNotFoundError(
                f"Expected output JSON not found at: {json_path}"
            )

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Output JSON is invalid: {e}") from e

        # Determine record count and columns
        if isinstance(data, list):
            record_count = len(data)
            columns = list(data[0].keys()) if data else []
        elif isinstance(data, dict):
            # Try to find the main data array
            for key, value in data.items():
                if isinstance(value, list) and value:
                    record_count = len(value)
                    columns = list(value[0].keys()) if value else []
                    break
            else:
                record_count = 1
                columns = list(data.keys())
        else:
            record_count = 0
            columns = []

        errors = []
        if record_count == 0:
            errors.append("No records found in output JSON")

        return TransformResult(
            json_path=json_path,
            record_count=record_count,
            columns=columns,
            errors=errors,
        )
