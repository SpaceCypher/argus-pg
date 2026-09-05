"""
Explanation Formatter for Argus-PG.

Generates human-readable explanations for bottlenecks and their resolutions
based on ExplainPlan data and ValidationResults.
"""

from argus.domain.index import IndexDefinition, ValidationResult
from argus.domain.plans import ExplainPlan, PlanNode


class ExplanationFormatter:
    """
    Formats bottleneck explanations by consuming ExplainPlan, IndexDefinition,
    and ValidationResult. Produces deterministic output matching planner evidence.
    """

    # Node types that indicate a potential bottleneck (full scans)
    _BOTTLENECK_NODE_TYPES = {"Seq Scan", "Parallel Seq Scan"}

    # Node types that indicate index usage (resolution)
    _INDEX_NODE_TYPES = {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}

    def format(
        self,
        before_plan: ExplainPlan,
        after_plan: ExplainPlan | None,
        index_def: IndexDefinition,
        result: ValidationResult,
    ) -> str:
        """
        Generate structured bottleneck explanation.

        Args:
            before_plan: The execution plan before the index was applied.
            after_plan: The execution plan after the index was applied (optional).
            index_def: The index definition that was tested.
            result: The validation result with cost comparison.

        Returns:
            A formatted multi-line string explaining the bottleneck and resolution.
        """
        lines: list[str] = []

        # --- Bottleneck Section ---
        lines.append("Bottleneck:")
        bottleneck_node = self._find_bottleneck_node(before_plan.plan)

        if bottleneck_node:
            node_type = bottleneck_node.node_type
            relation = bottleneck_node.relation_name or "unknown table"
            filter_cond = bottleneck_node.filter_condition
            rows = bottleneck_node.plan_rows

            lines.append(f"- Planner used {node_type} on {relation}")
            if filter_cond:
                lines.append(f"- Filtered on {filter_cond}")
            lines.append(f"- Estimated {rows} rows scanned")
        else:
            # Fallback if no clear bottleneck found
            lines.append(f"- Root node: {before_plan.plan.node_type}")
            lines.append(f"- Total cost: {before_plan.plan.total_cost}")

        lines.append("")  # Blank line separator

        # --- Resolution Section ---
        lines.append("Resolution:")

        index_name = index_def.inferred_name

        if after_plan:
            resolution_node = self._find_resolution_node(after_plan.plan)
            if resolution_node:
                new_node_type = resolution_node.node_type
                lines.append(f"- {new_node_type} after adding {index_name}")
            else:
                lines.append(f"- Plan changed after adding {index_name}")
        else:
            lines.append(f"- Index {index_name} applied")

        # Speedup factor
        factor = result.improvement_factor
        lines.append(f"- Speedup: {factor:.2f}x")

        # Cost comparison
        lines.append(f"- Cost: {result.original_cost:.2f} -> {result.new_cost:.2f}")

        return "\n".join(lines)

    def _find_bottleneck_node(self, node: PlanNode) -> PlanNode | None:
        """
        Recursively search for a bottleneck node (e.g., Seq Scan with filter).
        Returns the first bottleneck node found, or None.
        """
        if node.node_type in self._BOTTLENECK_NODE_TYPES:
            return node

        for child in node.plans:
            result = self._find_bottleneck_node(child)
            if result:
                return result

        return None

    def _find_resolution_node(self, node: PlanNode) -> PlanNode | None:
        """
        Recursively search for an index scan node.
        Returns the first index node found, or None.
        """
        if node.node_type in self._INDEX_NODE_TYPES:
            return node

        for child in node.plans:
            result = self._find_resolution_node(child)
            if result:
                return result

        return None
