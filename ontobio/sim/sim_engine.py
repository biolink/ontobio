from abc import ABCMeta, abstractmethod
from typing import Iterable, Dict, Optional
from ontobio.model.similarity import IcStatistic, AnnotationSufficiency, SimResult


class SimilarityEngine(metaclass=ABCMeta):
    """
    Interface for similarity engines, methods for search, compare
    """

    @abstractmethod
    def compare(self,
                profile_a: Iterable,
                profile_b: Iterable,
                method: Optional,
                filtr: Optional) -> SimResult:
        """
        Given a list of individuals,
        return a dictionary with their information content
        """
        pass

    @abstractmethod
    def search(self,
               profile: Iterable,
               method: Optional)-> SimResult:
        """
        Given an input profile, provides a ranking of similar profiles
        """
        pass


class InformationContentStore(metaclass=ABCMeta):
    """
    Interface for an IC cache or store needed
    for various computations - eg annotation sufficiency
    """

    @property
    @abstractmethod
    def statistics(self):
        pass

    @statistics.setter
    @abstractmethod
    def statistics(self, value: IcStatistic):
        pass

    @abstractmethod
    def get_profile_ic(self, profile: Iterable) -> Dict:
        """
        Given a list of individuals,
        return a dictionary with their information content
        """
        pass

    @abstractmethod
    def get_annotation_sufficiency(self, profile: Iterable)-> AnnotationSufficiency:
        """
        Given a list of individuals, return the annotation sufficiency
        scores
        """
        pass


