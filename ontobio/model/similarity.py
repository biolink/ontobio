"""
Dataclasses for ontobio.sim
"""
from dataclasses import dataclass, field
from typing import List, Optional, Union


@dataclass
class Node:
    """
    Basic node
    """
    id: str
    label: str = None


@dataclass
class ICNode(Node):
    """
    Node with information content
    """
    IC: float = None


@dataclass
class TypedNode(Node):
    """
    Node with type and optional taxon
    """
    type: str = None
    taxon: Optional[Node] = None


@dataclass
class SimMetadata():
    """
    Metadata returned with sim result
    """
    max_max_ic: float


@dataclass
class PairwiseMatch:
    """
    Data class for pairwise match
    """
    reference: ICNode
    match: ICNode
    lcs: ICNode


@dataclass
class SimMatch(TypedNode):
    """
    Data class similarity match
    """
    rank: Union[int, str] = None
    score: Union[float, int] = None
    significance: Union[float, str, None] = None
    pairwise_match: List[PairwiseMatch] = field(default_factory=list)


@dataclass
class SimQuery:
    """
    Data class for query
    """
    ids: List[Node]
    negated_ids: List[Node] = field(default_factory=list)
    unresolved_ids: List[str] = field(default_factory=list)
    target_ids: List[List[Node]] = field(default_factory=lambda: [[]])
    reference: TypedNode = None


@dataclass
class SimResult:
    """
    Data class similarity result
    """
    query: SimQuery
    matches: List[SimMatch]
    metadata: SimMetadata


@dataclass
class IcStatistic:
    """
    Data class for ic statistics

    mean_mean_ic: average of the average IC per individual
    mean_sum_ic: average sumIC per individual
    mean_cls: float, avg number of classes per individual
    max_max_ic: maximum IC of class annotated to an individual
    max_sum_ic: maximum sumIC
    individual_count: number of individuals
    mean_max_ic: average maxIC per individual
    """
    mean_mean_ic: float
    mean_sum_ic: float
    mean_cls: float
    max_max_ic: float
    max_sum_ic: float
    individual_count: int
    mean_max_ic: float
    descendants: List[str] = None


@dataclass
class AnnotationSufficiency:
    """
    Data class for annotation sufficiency object
    """
    simple_score: float
    scaled_score: float
    categorical_score: float
