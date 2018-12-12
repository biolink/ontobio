from ontobio.sim.api.interfaces import SimApi
from ontobio.config import get_config
from typing import Optional, List
from ontobio.vocabulary.similarity import SimAlgorithm
from ontobio.model.similarity import SimResult


class OwlSim3Api(SimApi):
    """
    OwlSim3 is the next iteration of owlsim and contains more algorithms
    than owlsim2 including several variations of the BOQA algorithm

    Ref:
    https://github.com/monarch-initiative/owlsim-v3
    http://owlsim3.monarchinitiative.org/api/docs/

    Status: not implemented
    """

    def __init__(self, url: Optional[str]=None, timeout: Optional[int]=None):
        self.url = url if url is not None else get_config().owlsim3.url
        self.timeout = timeout if timeout is not None else get_config().owlsim3.timeout

    def search(self,
               id_list: List,
               negated_classes: List,
               limit: Optional[int],
               method: Optional) -> List[SimResult]:
        """
        Given an input list of classes or individuals,
        provides a ranking of similar profiles
        """
        raise NotImplementedError

    def compare(self,
                query_classes: List,
                reference_classes: List,
                method: Optional) -> SimResult:
        """
        Given two lists of entites (classes, individual)
        return their similarity
        """
        raise NotImplementedError

    @staticmethod
    def matchers() -> List[SimAlgorithm]:
        """
        Matchers in owlsim3
        Could be dynamically retrieved from
        http://owlsim3.monarchinitiative.org/api/match/matchers
        """
        return [
            SimAlgorithm.PHENODIGM,
            SimAlgorithm.BAYES_NETWORK,
            SimAlgorithm.BAYES_VARIABLE,
            SimAlgorithm.NAIVE_BAYES_THREE_STATE,
            SimAlgorithm.NAIVE_BAYES_TWO_STATE,
            SimAlgorithm.NAIVE_BAYES_TWO_STATE_NO_BLANKET,
            SimAlgorithm.GRID,
            SimAlgorithm.GRID_NEGATED,
            SimAlgorithm.JACCARD,
            SimAlgorithm.MAX_INFORMATION
        ]

    def __str__(self):
        return "owlsim3 api: {}".format(self.url)
