from typing import List, Optional, Union


class Node:
    """
    Basic node
    """
    def __init__(self, id:Union[str,int], label:Optional[str]=None):
        self.id = id
        self.label = label

    def __str__(self):
        return self.id+' "'+str(self.label)+'"'


class SimMatch:
    """
    Data class similarity match
    """
    def __init__(self,
                 id: str,
                 label: str,
                 rank: int,
                 score: float,
                 type: Optional[str]=None,
                 taxon: Optional[Node]=None,
                 significance: Optional[float]=None):
        self.id = id
        self.label = label
        self.rank = rank
        self.score = score
        self.type = type
        self.taxon = taxon
        self.significance = significance


class SimQuery:
    """
    Data class for query
    """
    def __init__(self,
                 ids: List[Node],
                 negated_ids: Optional[List[Node]]=None,
                 unresolved_ids: Optional[List[str]]=None):
        self.ids = ids
        self.negated_ids = negated_ids if negated_ids is not None else []
        self.unresolved_ids = unresolved_ids if unresolved_ids is not None else []


class SimResult:
    """
    Data class similarity result
    """
    def __init__(self,
                 query: SimQuery,
                 matches: List[SimMatch]):
        self.query = query
        self.matches = matches


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
                 descendants: Optional[List[str]] = None):
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
