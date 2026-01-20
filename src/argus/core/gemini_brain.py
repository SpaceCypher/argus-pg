import json
import logging
import os
import re

import google.generativeai as genai
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
        self, api_key: str | None = None, model_name: str = "gemini-1.5-flash"
    ):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self._model_name = model_name
        self._configured = False

        if self._api_key:
            genai.configure(api_key=self._api_key)  # type: ignore
            self._model = genai.GenerativeModel(self._model_name)  # type: ignore
            self._configured = True
        else:
            logger.warning("GeminiBrain: No API Key. Returning empty suggestions.")

    async def propose_indexes(
        self, query: SqlStatement, plan: ExplainPlan
    ) -> list[IndexSuggestion]:
        if not self._configured:
            return []

        redacted_sql = self._redact_query(query.raw_query)
        prompt = self._build_prompt(redacted_sql, plan)

        try:
            # Recommend generate_content_async if available.
            # Assuming thread-safe context.
            response = await self._model.generate_content_async(prompt)

            return self._parse_response(response.text, query.query_id)

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
        # We pass the plan's cost and structure summary if possible, but keep it brief.
        # Constructing a comprehensive prompt.

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
