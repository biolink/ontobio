from abc import ABCMeta, abstractmethod
from typing import Iterable, Dict, Optional, List
from ontobio.model.similarity import IcStatistic, AnnotationSufficiency, SimResult
import numpy as np
from statistics import mean


class SimilarityEngine(metaclass=ABCMeta):
    """
    Interface for similarity engines, methods for search, compare
    """

    @abstractmethod
    def compare(self,
                entities_a: Iterable,
                entities_b: Iterable,
                method: Optional,
                filtr: Optional) -> SimResult:
        """
        Given two lists of entites (classes, individual)
        return their similarity
        """
        pass

    @abstractmethod
    def search(self,
               entities: Iterable,
               taxon_filter: int,
               category_filter: str,
               method: Optional)-> SimResult:
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

    @abstractmethod
    def get_annotation_sufficiency(
            self,
            profile: List[str],
            negated_classes: List[str],
            negation_weight: Optional[float] = .25,
            category_weight: Optional[float] = .5 )-> AnnotationSufficiency:
        """
        Given a list of individuals, return the annotation sufficiency
        scores
        """
        pass

    def _get_simple_score(self,
                          profile: List[str],
                          negated_classes: List[str],
                          bg_mean_pic: float,
                          bg_mean_max_pic: float,
                          bg_mean_sum_pic: float,
                          negation_weight: Optional[float] = .25,
                          ic_map: Optional[Dict[str, float]] = None) -> float:
        """
        Simple score is the average of the relative
        mean ic, max ic, and sum ic (relative to global stats)

        :param ic_map: dictionary of class - information content mappings
        :param bg_mean_pic: the average of the average IC in
                            the background profile annotations
        :param bg_max_pic: max IC annotated to the background set of profiles
        :param bg_mean_sum_pic: Average of the profile sum IC in background set
        :param negation_weight: Average of the profile sum IC in background set
        :param ic_map: Average of the profile sum IC in background set
        :return: simple score (float)
        """
        if ic_map is None:
            ic_map = self.get_profile_ic(profile + negated_classes)

        pos_map = {cls: ic for cls, ic in ic_map.items() if cls in profile}
        neg_map = {cls: ic for cls, ic in ic_map.items() if cls in negated_classes}

        mean_ic = mean(pos_map.values()) if len(profile) > 0 else 0
        max_ic = max(pos_map.values()) if len(profile) > 0 else 0
        sum_ic = sum(pos_map.values()) if len(profile) > 0 else 0

        if len(negated_classes) > 0:
            weighted_ic = [ic * negation_weight for ic in neg_map.values()]
            mean_ic = max([np.average([mean_ic, mean(neg_map.values())],
                                      weights=[1, negation_weight]),
                           mean_ic])
            max_ic = max([max_ic] + weighted_ic)
            sum_ic = sum_ic + sum(weighted_ic)

        return mean([
            min([mean_ic / bg_mean_pic, 1.0]),
            min([max_ic / bg_mean_max_pic, 1.0]),
            min([sum_ic / bg_mean_sum_pic, 1.0])
        ])

    def _get_scaled_score(
            self,
            simple_score: float,
            categorical_score: float,
            category_weight: Optional[float] = .5) -> float:
        """
        Scaled score is the weighted average of the simple score and
        categorical score
        """
        return np.average(
            [simple_score, categorical_score], weights=[1, category_weight]
        )

    def _get_categorical_score(
            self,
            profile: List,
            negated_classes: List,
            categories: List,
            negation_weight: Optional[float] = 1,
            ic_map: Optional[Dict[str, float]] = None) -> float:
        """
        The average of the simple scores across a list of categories
        """

        if ic_map is None:
            ic_map = self.get_profile_ic(profile + negated_classes)

        scores = []

        for cat in categories:
            if cat not in self.category_statistics:
                raise ValueError("statistics for {} not indexed".format(cat))

            pos_profile = [cls for cls in profile
                           if cls in self.category_statistics[cat].descendants]
            neg_profile = [cls for cls in negated_classes
                           if cls in self.category_statistics[cat].descendants]

            # Note that we're deviating from the publication
            # to match the reference java implementation where
            # mean_max_ic is replaced by max_max_ic
            scores.append(self._get_simple_score(
                pos_profile, neg_profile, self.category_statistics[cat].mean_mean_ic,
                self.category_statistics[cat].max_max_ic,
                self.category_statistics[cat].mean_sum_ic, negation_weight, ic_map
            ))
        return mean(scores)
