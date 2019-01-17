from typing import List, Optional, Union, Iterable


class Node:
    """
    Basic node
    """
    def __init__(self, id: Union[str,int], label: Optional[str]=None):
        self.id = id
        self.label = label

    def __str__(self):
        return self.id + ' "'+str(self.label)+'"'


class ICNode(Node):
    """
    Node with information content
    """

    def __init__(
            self,
            id: Union[str, int],
            IC: float,
            label: Optional[str] = None):
        super().__init__(id,label)
        self.IC = IC


class TypedNode(Node):
    """
    Node with type and optional taxon
    """

    def __init__(
            self,
            id: Union[str, int],
            type: str,
            label: Optional[str] = None,
            taxon: Optional[Node] = None):
        super().__init__(id,label)
        self.type = type
        self.taxon = taxon

class SimMetadata():
    """
    Metadata returned with sim result
    """

    def __init__(self, max_max_ic: float):
        self.max_max_ic = max_max_ic


class PairwiseMatch:
    """
    Data class for pairwise match
    """
    def __init__(self,
                 reference: ICNode,
                 match: ICNode,
                 lcs: ICNode):
        self.reference = reference
        self.match = match
        self.lcs = lcs  # lowest common subsumer


class SimMatch(TypedNode):
    """
    Data class similarity match
    """
    def __init__(self,
                 id: str,
                 label: str,
                 rank: Union[int, str],
                 score: Union[float, int],
                 type: Optional[str]=None,
                 taxon: Optional[Node]=None,
                 significance: Union[float, str, None]=None,
                 pairwise_match: Optional[List[PairwiseMatch]]=None):
        super().__init__(id, type, label, taxon)
        self.rank = rank
        self.score = score
        self.significance = significance
        self.pairwise_match = pairwise_match

        if self.pairwise_match is None:
            self.pairwise_match = []


class SimQuery:
    """
    Data class for query
    """
    def __init__(self,
                 ids: List[Node],
                 negated_ids: Optional[List[Node]]=None,
                 unresolved_ids: Optional[List[str]]=None,
                 target_ids: Optional[List[List[Node]]]=None,
                 reference: Optional[TypedNode]=None):
        """
        :param ids: list of classes (eg phenotypes)
        :param negated_ids: list of negated classes (eg phenotypes)
        :param unresolved_ids: list of unresolved classes
        :param target_ids: target classes (if in compare mode)
        :param reference: input reference individual or punned class
                          (eg gene, disease) if in compare mode
        """
        self.ids = ids
        self.negated_ids = negated_ids if negated_ids is not None else []
        self.unresolved_ids = unresolved_ids if unresolved_ids is not None else []
        self.target_ids = target_ids if target_ids is not None else [[]]
        self.reference = reference


class SimResult:
    """
    Data class similarity result
    """
    def __init__(self,
                 query: SimQuery,
                 matches: List[SimMatch],
                 metadata: SimMetadata):
        self.query = query
        self.matches = matches
        self.metadata = metadata


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
    def __init__(self,
                 mean_mean_ic: float,
                 mean_sum_ic: float,
                 mean_cls: float,
                 max_max_ic: float,
                 max_sum_ic: float,
                 individual_count: int,
                 mean_max_ic: float,
                 descendants: Optional[Iterable[str]] = None):
        self.mean_mean_ic = mean_mean_ic
        self.mean_sum_ic = mean_sum_ic
        self.mean_cls = mean_cls
        self.max_max_ic = max_max_ic
        self.max_sum_ic = max_sum_ic
        self.individual_count = individual_count
        self.mean_max_ic = mean_max_ic
        self.descendants = descendants if descendants is not None else []
        return


class AnnotationSufficiency:
    """
    Data class for annotation sufficiency object
    """
    def __init__(self,
                 simple_score: float,
                 scaled_score: float,
                 categorical_score: float):
        self.simple_score = simple_score
        self.scaled_score = scaled_score
        self.categorical_score = categorical_score
        return
