from argus.domain.plans import ExplainPlan, PlanNode


class Analyzer:
    """
    Analyzes ExplainPlan objects to extract insights and metrics.
    Pure logic component - does not execute methods.
    """

    def __init__(self, plan: ExplainPlan):
        self.plan = plan

    def get_total_cost(self) -> float:
        """
        Returns the total estimated startup + run cost of the plan.
        """
        return self.plan.plan.total_cost

    def find_nodes(self, node_type: str) -> list[PlanNode]:
        """
        Recursively finds all nodes matching the given Node Type (case-insensitive).
        """
        results: list[PlanNode] = []
        self._recursive_find(self.plan.plan, node_type.lower(), results)
        return results

    def _recursive_find(
        self, node: PlanNode, target_type_lower: str, results: list[PlanNode]
    ) -> None:
        if node.node_type.lower() == target_type_lower:
            results.append(node)

        for child in node.plans:
            self._recursive_find(child, target_type_lower, results)

    def uses_index_scan(self, index_name: str | None = None) -> bool:
        """
        Checks if the plan invokes an Index Scan (or Index Only Scan).
        If index_name is provided, checks if that specific index is used.
        """
        # Node types to check
        index_types = {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}

        # We can implement a generic check traversal
        return self._recursive_check_index(self.plan.plan, index_types, index_name)

    def _recursive_check_index(
        self, node: PlanNode, index_types: set[str], target_index: str | None
    ) -> bool:
        # Check current node
        if node.node_type in index_types:
            # If target index specified, check name
            if target_index:
                # We now have index_name in the model
                if node.index_name == target_index:
                    return True
                # If checking specific index and it doesn't match, search children
                # (unlikely to have children for an Index Scan, but safe default)
            else:
                return True

        for child in node.plans:
            if self._recursive_check_index(child, index_types, target_index):
                return True

        return False
