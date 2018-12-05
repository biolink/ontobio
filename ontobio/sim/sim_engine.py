from abc import ABCMeta, abstractmethod
from typing import Optional, Iterable
from ontobio.model.similarity import SimResult


class SimilarityEngine(metaclass=ABCMeta):
    """
    Interface for similarity engines, methods for search and compare

    Differs from ontobio.sim.api.interfaces.SimApi in that a
    similarity engine is type specific, eg phenotype, go term
    and handles individuals appropriately
    """

    @abstractmethod
    def compare(self,
                reference_ids: Iterable,
                query_profiles: Iterable[Iterable],
                method: Optional) -> SimResult:
        """
        Given two lists of entities (classes, individuals),
        resolves them to some type (phenotypes, go terms, etc) and
        returns their similarity
        """
        pass

    @abstractmethod
    def search(self,
               id_list: Iterable,
               negated_ids: Iterable,
               limit: Optional[int],
               taxon_filter: Optional,
               category_filter: Optional,
               method: Optional)-> SimResult:
        """
        Given an input iterable of classes or individuals,
        resolves to target classes (phenotypes, go terms, etc)
        and provides a ranking of similar profiles
        """
        pass
