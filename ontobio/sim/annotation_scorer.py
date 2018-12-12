from typing import Optional, List, Dict
from ontobio.model.similarity import AnnotationSufficiency
from ontobio.vocabulary.upper import HpoUpperLevel
from ontobio.sim.api.interfaces import InformationContentStore
import numpy as np
from statistics import mean


class AnnotationScorer:
    """
    Computes the annotation sufficiency scores as described
    by https://zenodo.org/record/834091#.W8ZnCxhlCV4
    """

    def __init__(self, ic_store: InformationContentStore):
        self.ic_store = ic_store

    def get_annotation_sufficiency(
            self,
            profile: List[str],
            negated_classes: List[str],
            categories: Optional[List] = None,
            negation_weight: Optional[float] = .25,
            category_weight: Optional[float] = .5) -> AnnotationSufficiency:
        """
        Given a list of individuals, return the simple, scaled, and categorical scores
        """

        if categories is None:
            categories = [enum.value for enum in HpoUpperLevel]
        ic_map = self.ic_store.get_profile_ic(profile + negated_classes)

        # Simple score is the weighted average of the present and
        # explicitly stated negative/absent phenotypes
        #
        # Note that we're deviating from the publication
        # to match the reference java implementation where
        # mean_max_ic is replaced with max_max_ic:
        # https://github.com/owlcollab/owltools/blob/452b4a/
        # OWLTools-Sim/src/main/java/owltools/sim2/AbstractOwlSim.java#L1038
        simple_score = self._get_simple_score(
            profile, negated_classes, self.ic_store.statistics.mean_mean_ic,
            self.ic_store.statistics.max_max_ic, self.ic_store.statistics.mean_sum_ic,
            negation_weight, ic_map
        )

        categorical_score = self._get_categorical_score(
            profile, negated_classes, categories,
            negation_weight, ic_map
        )
        scaled_score = self._get_scaled_score(
            simple_score, categorical_score, category_weight)

        return AnnotationSufficiency(
            simple_score=simple_score,
            scaled_score=scaled_score,
            categorical_score=categorical_score
        )

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
        :param bg_mean_max_pic: max IC annotated to the background set of profiles
        :param bg_mean_sum_pic: Average of the profile sum IC in background set
        :param negation_weight: Average of the profile sum IC in background set
        :param ic_map: Average of the profile sum IC in background set
        :return: simple score (float)
        """
        if ic_map is None:
            ic_map = self.ic_store.get_profile_ic(profile + negated_classes)

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

    @staticmethod
    def _get_scaled_score(
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
            ic_map = self.ic_store.get_profile_ic(profile + negated_classes)

        scores = []

        for cat in categories:
            if cat not in self.ic_store.category_statistics:
                raise ValueError("statistics for {} not indexed".format(cat))

            pos_profile = [cls for cls in profile
                           if cls in self.ic_store.category_statistics[cat].descendants]
            neg_profile = [cls for cls in negated_classes
                           if cls in self.ic_store.category_statistics[cat].descendants]

            # Note that we're deviating from the publication
            # to match the reference java implementation where
            # mean_max_ic is replaced by max_max_ic
            scores.append(self._get_simple_score(
                pos_profile, neg_profile,
                self.ic_store.category_statistics[cat].mean_mean_ic,
                self.ic_store.category_statistics[cat].max_max_ic,
                self.ic_store.category_statistics[cat].mean_sum_ic,
                negation_weight, ic_map
            ))
        return mean(scores)
