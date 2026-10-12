"""
Guaranteed Service Model (GSM) - Core Model Logic.
Implements the echelon stock formulation for unified (multi-tier) inventory networks.
"""
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import cached_property
from typing import Dict, List, Optional


@dataclass
class GSMNode:
    """Represents a stocking location in the supply chain network."""
    id: str
    type: str                        # "Supplier" | "DC" | "Store"
    processing_time: int             # Days to process/produce
    demand_mean: float = 0.0         # Daily demand mean
    demand_std: float = 0.0          # Daily demand std dev
    holding_cost: float = 0.0        # Holding cost per unit per day
    ordering_cost: float = 0.0       # Fixed cost per replenishment order
    max_s_out: int = 30              # Maximum outbound service time
    min_s_out: int = 0               # Minimum outbound service time
    service_level: float = 0.95      # Target cycle service level
    location_id: Optional[str] = None
    product_id: Optional[str] = None


@dataclass
class GSMEdge:
    """Represents a transportation lane between two nodes."""
    source: str
    target: str
    transit_time: int                # Days in transit (lead time on this lane)


@dataclass
class GSMNetwork:
    """
    Full GSM supply chain network.
    Validates topology and exposes helper methods for the solver.
    """
    nodes: List[GSMNode] = field(default_factory=list)
    edges: List[GSMEdge] = field(default_factory=list)

    @cached_property
    def _preds(self) -> Dict[str, List[str]]:
        preds: Dict[str, List[str]] = defaultdict(list)
        for e in self.edges:
            preds[e.target].append(e.source)
        return preds

    @cached_property
    def _succs(self) -> Dict[str, List[str]]:
        succs: Dict[str, List[str]] = defaultdict(list)
        for e in self.edges:
            succs[e.source].append(e.target)
        return succs

    @cached_property
    def _transit(self) -> Dict[tuple, int]:
        return {(e.source, e.target): e.transit_time for e in self.edges}

    def node_map(self) -> Dict[str, GSMNode]:
        return {n.id: n for n in self.nodes}

    def predecessors(self, node_id: str) -> List[str]:
        """Returns all upstream nodes feeding into node_id."""
        return list(self._preds.get(node_id, []))

    def successors(self, node_id: str) -> List[str]:
        """Returns all downstream nodes fed from node_id."""
        return list(self._succs.get(node_id, []))

    def transit_time(self, source: str, target: str) -> int:
        return self._transit.get((source, target), 0)

    def source_nodes(self) -> List[str]:
        """Nodes with no predecessors (e.g. raw material suppliers)."""
        return [n.id for n in self.nodes if not self._preds.get(n.id)]

    def sink_nodes(self) -> List[str]:
        """Nodes with no successors (e.g. stores or customers)."""
        return [n.id for n in self.nodes if not self._succs.get(n.id)]

    def topological_order(self) -> List[str]:
        """Kahn's algorithm. Nodes on a cycle are omitted."""
        in_degree = {n.id: len(self._preds.get(n.id, [])) for n in self.nodes}
        queue = deque(n.id for n in self.nodes if in_degree[n.id] == 0)
        order = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for nxt in self._succs.get(node, []):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)
        return order

    def validate(self) -> List[str]:
        """Sanity checks before solving."""
        errors = []
        node_ids = [n.id for n in self.nodes]
        if not node_ids:
            return ["Network has no nodes."]

        seen = set()
        for n_id in node_ids:
            if n_id in seen:
                errors.append(f"Duplicate node id '{n_id}'.")
            seen.add(n_id)

        lanes = set()
        for e in self.edges:
            if e.source not in seen:
                errors.append(f"Edge source '{e.source}' not in nodes.")
            if e.target not in seen:
                errors.append(f"Edge target '{e.target}' not in nodes.")
            if e.transit_time < 0:
                errors.append(f"Edge from '{e.source}' to '{e.target}' has negative transit time.")
            if (e.source, e.target) in lanes:
                errors.append(f"Duplicate edge from '{e.source}' to '{e.target}'.")
            lanes.add((e.source, e.target))

        for n in self.nodes:
            if n.holding_cost < 0:
                errors.append(f"Node '{n.id}' has negative holding cost.")
            if n.ordering_cost < 0:
                errors.append(f"Node '{n.id}' has negative ordering cost.")
            if n.processing_time < 0:
                errors.append(f"Node '{n.id}' has negative processing time.")
            if n.demand_mean < 0 or n.demand_std < 0:
                errors.append(f"Node '{n.id}' has negative demand metrics.")
            if n.min_s_out < 0 or n.min_s_out > n.max_s_out:
                errors.append(f"Node '{n.id}' has invalid service time bounds.")
            if not 0 < n.service_level < 1:
                errors.append(f"Node '{n.id}' service level must be between 0 and 1.")

        if errors:
            return errors

        if len(self.topological_order()) != len(self.nodes):
            errors.append("Circular supply loop detected in the network.")

        if len(self.nodes) > 1:
            for n in self.nodes:
                if not self._preds.get(n.id) and not self._succs.get(n.id):
                    errors.append(f"Node '{n.id}' is disconnected from the network.")

        return errors


def build_network_from_dicts(nodes: List[Dict], edges: List[Dict]) -> GSMNetwork:
    """Factory to build a GSMNetwork from plain dictionaries (e.g. from API payload)."""
    node_fields = GSMNode.__dataclass_fields__
    edge_fields = GSMEdge.__dataclass_fields__
    gsm_nodes = [GSMNode(**{k: v for k, v in n.items() if k in node_fields}) for n in nodes]
    gsm_edges = [GSMEdge(**{k: v for k, v in e.items() if k in edge_fields}) for e in edges]
    return GSMNetwork(nodes=gsm_nodes, edges=gsm_edges)
