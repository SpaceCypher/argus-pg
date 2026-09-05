import asyncio
import json
import logging
import os
import re
from typing import Any

from google import genai
from pydantic import ValidationError

from argus.core.brain import Brain
from argus.domain.index import IndexDefinition, IndexSuggestion
from argus.domain.plans import ExplainPlan
from argus.domain.query import SqlStatement

logger = logging.getLogger(__name__)


class GeminiBrain(Brain):
    """
    Brain implementation that uses Google Gemini API to suggest optimizations.
    Constraints: Indexes only, no rewrite suggestions. Silently fails on API errors.
    """

    # Regex to redact string literals ('...') and numeric literals
    _STRING_LITERAL_PATTERN = re.compile(r"'[^']*'")
    _NUMERIC_LITERAL_PATTERN = re.compile(r"\b\d+\.?\d*\b")

    def __init__(
        self, api_key: str | None = None, model_name: str = "gemini-3.5-flash"
    ):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model_name = model_name
        self._configured = False
        self._client = None

        if self._api_key:
            # New client initialization
            # The client gets the API key from the environment variable `GEMINI_API_KEY` or constructor.
            # We explicitly pass it here if provided/found.
            # Note: The new library might expect GOOGLE_API_KEY or GEMINI_API_KEY.
            # We will rely on passing it explicitly if we have it.
            # but the SDK might prefer env vars.
            os.environ["GEMINI_API_KEY"] = self._api_key
            try:
                self._client = genai.Client(api_key=self._api_key)
                self._configured = True
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}")
        else:
            logger.warning("GeminiBrain: No API Key. Returning empty suggestions.")

    async def propose_indexes(
        self, query: SqlStatement, plan: ExplainPlan
    ) -> list[IndexSuggestion]:
        if not self._configured or not self._client:
            return []

        redacted_sql = self._redact_query(query.raw_query)
        prompt = self._build_prompt(redacted_sql, plan)

        try:
            client = self._client
            if hasattr(client, "aio"):
                response: Any = await client.aio.models.generate_content(
                    model=self._model_name, contents=prompt
                )
            else:
                loop = asyncio.get_running_loop()

                def _call() -> Any:
                    return client.models.generate_content(
                        model=self._model_name, contents=prompt
                    )

                response = await loop.run_in_executor(None, _call)

            response_text = getattr(response, "text", None)
            if response_text and isinstance(response_text, str):
                return self._parse_response(response_text, str(query.query_id))
            return []

        except Exception as e:
            # Silent degradation
            logger.warning(f"Gemini API failed: {e}")
            return []

    def _redact_query(self, sql: str) -> str:
        """
        Replaces literals with placeholders to minimize data leakage.
        """
        sql = self._STRING_LITERAL_PATTERN.sub("'?'", sql)
        sql = self._NUMERIC_LITERAL_PATTERN.sub("?", sql)
        return sql

    def _build_prompt(self, sql: str, plan: ExplainPlan) -> str:
        # Minimal deterministic prompt
        return f"""
You are an expert PostgreSQL DBA. Analyze the following query and execution plan.
Your task is to suggest INDEXES ONLY. Do not suggest query rewrites.
Return a JSON object with a key "suggestions" containing a list of objects.
Each object must have:
- "table_name": str
- "columns": list[str]
- "method": "btree" | "gin" | "gist" | "brin" | "hash"
- "reasoning": str (concise explanation)

Query (redacted):
{sql}

Plan Cost: {plan.plan.total_cost}
Plan Structure (simplified):
{plan.plan.model_dump_json(
    include={'node_type', 'relation_name', 'alias', 'filter_condition'},
    exclude_none=True
)}

Output JSON ONLY.
"""

    def _parse_response(self, text: str, query_id: str) -> list[IndexSuggestion]:
        # Handle potential markdown code blocks
        clean_text = text.strip()
        if clean_text.startswith("```"):
            clean_text = clean_text.replace("```json", "").replace("```", "")

        try:
            data = json.loads(clean_text)
            suggestions = []
            for item in data.get("suggestions", []):
                try:
                    # Construct IndexDefinition
                    idx_def = IndexDefinition(
                        table_name=item["table_name"],
                        # Default schema to public if not explicit.
                        schema_name="public",
                        columns=item["columns"],
                        method=item.get("method", "btree"),
                        unique=False,
                    )

                    suggestions.append(
                        IndexSuggestion(
                            target_query_id=query_id,
                            definition=idx_def,
                            reasoning=item["reasoning"],
                        )
                    )
                except (ValidationError, KeyError) as e:
                    logger.warning(f"Failed to parse index suggestion item: {e}")
                    continue
            return suggestions

        except json.JSONDecodeError:
            logger.warning("Failed to decode Gemini JSON response.")
            return []
