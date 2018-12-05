from abc import ABCMeta, abstractmethod
from typing import Iterable, Optional, List, Dict
from ontobio.model.similarity import SimResult, IcStatistic
from ontobio.vocabulary.similarity import SimAlgorithm


class SimApi(metaclass=ABCMeta):

    @abstractmethod
    def search(self,
               id_list: Iterable,
               negated_classes: Iterable,
               limit: Optional[int],
               method: Optional) -> List[SimResult]:
        """
        Given an input list of classes, searches for similar lists of classes
        and provides a ranked list of matches
        """
        pass

    @abstractmethod
    def compare(self,
                query_classes: Iterable,
                reference_classes: Iterable,
                method: Optional) -> SimResult:
        """
        Given two lists of classes return their similarity
        """
        pass

    @staticmethod
    @abstractmethod
    def matchers() -> List[SimAlgorithm]:
        """
        Return the list of available matchers (eg resnik, boqa, cosine)
        could theoretically be a property with no setter
        """
        pass


class FilteredSearchable(metaclass=ABCMeta):

    @abstractmethod
    def filtered_search(self,
               id_list: Iterable,
               negated_classes: Iterable,
               limit: Optional[int],
               taxon_filter: Optional,
               category_filter: Optional,
               method: Optional) -> SimResult:
        """
        Given an input iterable of classes or individuals,
        provides a ranking of similar profiles
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

    @property
    @abstractmethod
    def category_statistics(self):
        pass

    @category_statistics.setter
    @abstractmethod
    def category_statistics(self, value: Dict[str, IcStatistic]):
        pass

    @abstractmethod
    def get_profile_ic(self, profile: Iterable) -> Dict[str, float]:
        """
        Given a list of individuals,
        return a dictionary with their information content
        """
        pass
