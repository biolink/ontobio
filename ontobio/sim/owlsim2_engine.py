from ontobio.sim.sim_engine import InformationContentStore, SimilarityEngine
from typing import Iterable, Dict, Union, Optional
from ontobio.model.similarity import IcStatistic, AnnotationSufficiency, SimResult
from ontobio.config import get_config
from ontobio.vocabulary.similarity import SimAlgorithm
from json.decoder import JSONDecodeError
import requests

CONFIG = get_config()


class OwlSim2Engine(InformationContentStore, SimilarityEngine):

    OWLSIM_URL = CONFIG.owlsim2.url
    OWLSIM_TIMEOUT = CONFIG.owlsim2.timeout

    def __init__(self):
        self._statistics = self._get_owlsim_stats()

    @property
    def statistics(self) -> IcStatistic:
        return self._statistics

    @statistics.setter
    def statistics(self, value):
        self._statistics = value

    def search(
            self,
            profile: Iterable,
            method: Union[SimAlgorithm, str, None] = SimAlgorithm.PHENODIGM
    ) -> SimResult:
        if method is not SimAlgorithm.PHENODIGM:
            raise NotImplementedError("Sim method not implemented in owlsim2")
        return

    def compare(self,
                profile_a: Iterable,
                profile_b: Iterable,
                method: SimAlgorithm.PHENODIGM,
                filtr: Optional) -> SimResult:
        raise NotImplementedError

    def get_profile_ic(self, profile: Iterable) -> Dict:
        """
        Given a list of individuals, return their information content
        """
        owlsim_url = OwlSim2Engine.OWLSIM_URL + 'getAttributeInformationProfile'
        params = {'a': profile}
        sim_request = requests.get(
            owlsim_url, params=params, timeout=OwlSim2Engine.OWLSIM_TIMEOUT)
        sim_response = sim_request.json()

        profile_ic = {}
        try:
            for cls in sim_response['input']:
                profile_ic[cls['id']] = cls['IC']
        except JSONDecodeError as exc_msg:
            raise JSONDecodeError("Cannot parse owlsim2 response: {}".format(exc_msg))

        return profile_ic

    @staticmethod
    def _get_owlsim_stats() -> IcStatistic:
        owlsim_url = OwlSim2Engine.OWLSIM_URL + 'getAttributeInformationProfile'
        sim_request = requests.get(owlsim_url, timeout=OwlSim2Engine.OWLSIM_TIMEOUT)
        sim_response = sim_request.json()

        try:
            ic_statistics = IcStatistic(
                mean_mean_ic = float(sim_response['system_stats']['meanMeanIC']),
                mean_sum_ic = float(sim_response['system_stats']['meanSumIC']),
                mean_cls = float(sim_response['system_stats']['meanN']),
                max_max_ic = float(sim_response['system_stats']['maxMaxIC']),
                max_sum_ic = float(sim_response['system_stats']['maxSumIC']),
                individual_count = int(sim_response['system_stats']['individuals']),
                mean_max_ic = float(sim_response['system_stats']['meanMaxIC'])
            )
        except JSONDecodeError as exc_msg:
            raise JSONDecodeError("Cannot parse owlsim2 response: {}".format(exc_msg))

        return ic_statistics

    def get_annotation_sufficiency(self, profile: Iterable) -> AnnotationSufficiency:
        pass

    def _get_simple_score(self, profile: Iterable) -> float:
        pass

    def _get_scaled_score(self, profile: Iterable) -> float:
        pass

    def _get_categorical_score(self, profile: Iterable) -> float:
        pass