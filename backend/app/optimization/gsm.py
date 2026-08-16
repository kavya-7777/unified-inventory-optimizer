"""
Guaranteed Service Model (GSM) - Core Model Logic.
Implements the echelon stock formulation for multi-echelon inventory networks.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class GSMNode:
    """Represents a stocking location in the supply chain network."""
    id: str
    type: str                        # "Supplier" | "DC" | "Store"
    processing_time: int             # Days to process/produce
    demand_mean: float = 0.0         # Daily demand mean (relevant at end nodes)
    demand_std: float = 0.0          # Daily demand std dev
    holding_cost: float = 0.0        # Holding cost per unit per day
    max_s_out: int = 30              # Maximum outbound service time
    min_s_out: int = 0               # Minimum outbound service time
    service_level: float = 0.95      # Target service level (used for Z lookup)


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

    def node_map(self) -> Dict[str, GSMNode]:
        return {n.id: n for n in self.nodes}

    def predecessors(self, node_id: str) -> List[str]:
        """Returns all upstream nodes feeding into node_id."""
        return [e.source for e in self.edges if e.target == node_id]

    def successors(self, node_id: str) -> List[str]:
        """Returns all downstream nodes fed from node_id."""
        return [e.target for e in self.edges if e.source == node_id]

    def transit_time(self, source: str, target: str) -> int:
        for e in self.edges:
            if e.source == source and e.target == target:
                return e.transit_time
        return 0

    def source_nodes(self) -> List[str]:
        """Nodes with no predecessors (e.g. raw material suppliers)."""
        targets = {e.target for e in self.edges}
        return [n.id for n in self.nodes if n.id not in targets]

    def sink_nodes(self) -> List[str]:
        """Nodes with no successors (e.g. stores or customers)."""
        sources = {e.source for e in self.edges}
        return [n.id for n in self.nodes if n.id not in sources]

    def validate(self) -> List[str]:
        """Basic sanity checks before solving."""
        errors = []
        node_ids = {n.id for n in self.nodes}
        for e in self.edges:
            if e.source not in node_ids:
                errors.append(f"Edge source '{e.source}' not in nodes.")
            if e.target not in node_ids:
                errors.append(f"Edge target '{e.target}' not in nodes.")
        for n in self.nodes:
            if n.holding_cost < 0:
                errors.append(f"Node '{n.id}' has negative holding cost.")
            if n.processing_time < 0:
                errors.append(f"Node '{n.id}' has negative processing time.")
        return errors


def build_network_from_dicts(nodes: List[Dict], edges: List[Dict]) -> GSMNetwork:
    """Factory to build a GSMNetwork from plain dictionaries (e.g. from API payload)."""
    gsm_nodes = [GSMNode(**{k: v for k, v in n.items() if k in GSMNode.__dataclass_fields__}) for n in nodes]
    gsm_edges = [GSMEdge(**e) for e in edges]
    return GSMNetwork(nodes=gsm_nodes, edges=gsm_edges)
