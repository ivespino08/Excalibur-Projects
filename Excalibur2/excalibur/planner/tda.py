"""Task Difficulty Assessment (TDA) — computes the Task Difficulty Index for attack tree nodes."""

from __future__ import annotations

from excalibur.planner.models import AttackNode, AttackTree, TDIScore


class TDAComputer:
    """Computes the Task Difficulty Index for attack tree nodes.

    The TDI combines four dimensions — horizon depth, success rate,
    context load, and evidence confidence — into a single scalar that
    drives node selection, mode switching, and pruning decisions.
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self.weights: dict[str, float] = weights or {
            "horizon": 0.3,
            "evidence": 0.3,
            "context": 0.2,
            "success": 0.2,
        }

    def compute_tdi(
        self,
        node: AttackNode,
        tree: AttackTree,
        context_load: float = 0.0,
        llm_horizon: float | None = None,
    ) -> TDIScore:
        """Compute the TDI for a given node within its tree context.

        Args:
            node: The attack node to evaluate.
            tree: The full attack tree (needed for path traversal).
            context_load: Current token-budget utilization ratio (0..1).
            llm_horizon: Optional LLM-judged horizon estimate (0..1, where
                0.0 = very close to goal, 1.0 = very far), per §4.3.1's
                horizon estimation dimension. This is a genuine *prediction*
                of remaining steps and is what the paper's calibration
                figures (MAE 4.2 steps, Spearman's rho=0.71) describe; it
                requires an LLM call and is computed by the caller (see
                AgentController._estimate_horizon_llm), since TDAComputer
                itself has no backend access. When ``None`` (LLM call
                unavailable or failed), falls back to a deterministic
                tree-structure proxy -- see ``_estimate_horizon_fallback``.

        Returns:
            A fully populated ``TDIScore``.
        """
        if llm_horizon is not None:
            horizon = max(0.0, min(1.0, llm_horizon))
        else:
            horizon = self._estimate_horizon_fallback(node, tree)
        success_rate = self._compute_success_rate(node)
        evidence_confidence = self._compute_evidence_confidence(node, tree)
        return TDIScore(
            horizon=horizon,
            success_rate=success_rate,
            context_load=context_load,
            evidence_confidence=evidence_confidence,
            weight_horizon=self.weights["horizon"],
            weight_evidence=self.weights["evidence"],
            weight_context=self.weights["context"],
            weight_success=self.weights["success"],
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _estimate_horizon_fallback(self, node: AttackNode, tree: AttackTree) -> float:
        """Return a normalised depth ranking for *node*, as a fallback.

        This is a deterministic tree-structure proxy used only when an
        LLM-judged horizon estimate isn't available. It measures how deep
        *node* already is, which is not the same thing as steps remaining
        to the goal -- it's a stand-in, not an equivalent.
        """
        path = tree.get_path_to_root(node.id)
        depth = len(path)
        max_depth = max(
            (len(tree.get_path_to_root(n.id)) for n in tree.nodes.values()),
            default=1,
        )
        return min(depth / max(max_depth, 1), 1.0)

    @staticmethod
    def _compute_success_rate(node: AttackNode) -> float:
        """Laplace-smoothed success rate: (successes + 1) / (visits + 2)."""
        return (node.success_count + 1) / (node.visit_count + 2)

    @staticmethod
    def _compute_evidence_confidence(
        node: AttackNode,
        tree: AttackTree,
    ) -> float:
        """Mean evidence confidence along the path from *node* to the root.

        The root node is excluded per Appendix C: it represents the initial
        state before any evidence is gathered, and including it would
        artificially inflate confidence (especially for shallow paths).
        """
        path = tree.get_path_to_root(node.id)
        # get_path_to_root returns [node, ..., root]; drop the root if the
        # path has more than just the root itself.
        if len(path) > 1:
            path = path[:-1]
        if not path:
            return 0.5
        return sum(n.evidence_level.value for n in path) / len(path)
