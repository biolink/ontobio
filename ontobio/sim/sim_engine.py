from abc import ABCMeta, abstractmethod
from typing import Iterable, Optional
from ontobio.model.similarity import SimResult


class SimilarityEngine(metaclass=ABCMeta):
    """
    Interface for similarity engines, methods for search, compare
    """

    @abstractmethod
    def compare(self,
                entities_a: Iterable,
                entities_b: Iterable,
                method: Optional) -> SimResult:
        """
        Given two lists of entites (classes, individual)
        return their similarity
        """
        pass

    @abstractmethod
    def search(self,
               id_list: Iterable,
               negated_ids: Iterable,
               taxon_filter: int,
               category_filter: str,
               method: Optional)-> SimResult:
        """
        Given an input iterable of classes or individuals,
        provides a ranking of similar profiles
        """
        pass