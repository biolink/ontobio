from ontobio.sim.api.interfaces import SimApi, InformationContentStore, FilteredSearchable
from ontobio.config import get_config
from ontobio.vocabulary.upper import HpoUpperLevel
from ontobio.ontol_factory import OntologyFactory
from ontobio.model.similarity import IcStatistic
from ontobio.vocabulary.similarity import SimAlgorithm

from typing import List, Optional, Dict, Tuple
from json.decoder import JSONDecodeError
from cachier import cachier
import datetime
import requests


class OwlSim2Api(SimApi, InformationContentStore, FilteredSearchable):
    """
    Owlsim2 is part of the owltools package and uses a modified
    version of the phenodigm algorithm to compute semantic similarity,
    using IC instead of the geometric mean of IC and jaccard similarities,
    as well as jaccard and SimGIC

    refs:
      code: https://github.com/owlcollab/owltools/tree/master/OWLTools-Sim
      phendigm: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3649640/
      simGIC:  https://bmcbioinformatics.biomedcentral.com/articles/
               10.1186/1471-2105-9-S5-S4

    The monarch instance computes similarity over phenotype profiles,
    so this API refers to phenotypes as input and phenotypic similarity
    """

    def __init__(self, url: Optional[str]=None, timeout: Optional[int]=None):
        self.url = url if url is not None else get_config().owlsim2.url
        self.timeout = timeout if timeout is not None else get_config().owlsim2.timeout

        # Init ic stats
        stats = self._get_owlsim_stats()
        self._statistics = stats[0]
        self._category_statistics = stats[1]

    @property
    def statistics(self) -> IcStatistic:
        return self._statistics

    @statistics.setter
    def statistics(self, value):
        self._statistics = value

    @property
    def category_statistics(self):
        return self._category_statistics

    @category_statistics.setter
    def category_statistics(self, value: Dict[str, IcStatistic]):
        self._category_statistics = value

    def search(self):
        pass

    def compare(self):
        pass

    def filtered_search(self,
               id_list: List,
               taxon_filter: int,
               category_filter: str,
               method: Optional) -> SimResult:
        """
        Given an input iterable of classes or individuals,
        provides a ranking of similar profiles
        """
        pass

    @staticmethod
    def matchers() -> List[SimAlgorithm]:
        """
        Matchers in owlsim2
        """
        return [
            SimAlgorithm.PHENODIGM,
            SimAlgorithm.JACCARD,
            SimAlgorithm.SIM_GIC
        ]

    def get_profile_ic(self, profile: List) -> Dict:
        """
        Given a list of individuals, return their information content
        """
        sim_response = self.get_attribute_information_profile(profile)

        profile_ic = {}
        try:
            for cls in sim_response['input']:
                profile_ic[cls['id']] = cls['IC']
        except JSONDecodeError as exc_msg:
            raise JSONDecodeError("Cannot parse owlsim2 response: {}".format(exc_msg))

        return profile_ic

    def search_by_attribute_set(
            self,
            profile: List[str],
            namespace_filter: Optional[str]=None) -> Dict:
        """
        Given a list of phenotypes, returns a ranked list of individuals
        individuals can be filtered by namespace, eg MONDO, MGI, HGNC
        :raises JSONDecodeError: If the response body does not contain valid json.
        """
        owlsim_url = self.url + 'searchByAttributeSet'

        params = {
            'a': profile,
            'target': namespace_filter
        }
        return requests.get(owlsim_url, params=params, timeout=self.timeout).json()

    def compare_attribute_sets(
            self,
            profile_a: List[str],
            profile_b: List[str],
            namespace_filter: Optional[str] = None) -> Dict:
        """
        Given two phenotype profiles
        :raises JSONDecodeError: If the response body does not contain valid json.
        """
        owlsim_url = self.url + 'compareAttributeSets'

        params = {
            'a': profile_a,
            'b': profile_b,
            'target': namespace_filter
        }
        return requests.get(owlsim_url, params=params, timeout=self.timeout).json()

    def get_attribute_information_profile(
            self,
            profile: Optional[List[str]]=None,
            categories: Optional[List[str]]=None) -> Dict:
        """
        Get the information content for a list of phenotypes
        and the annotation sufficiency simple and
        and categorical scores if categories are provied

        Ref: https://zenodo.org/record/834091#.W8ZnCxhlCV4
        Note that the simple score varies slightly from the pub in that
        it uses max_max_ic instead of mean_max_ic

        If no arguments are passed this function returns the
        system (loaded cohort) stats
        :raises JSONDecodeError: If the response body does not contain valid json.
        """
        owlsim_url = self.url + 'getAttributeInformationProfile'

        params = {
            'a': profile,
            'r': categories
        }
        return requests.get(owlsim_url, params=params, timeout=self.timeout).json()

    @cachier(datetime.timedelta(days=30))
    def _get_owlsim_stats(self) -> Tuple[IcStatistic, Dict[str, IcStatistic]]:
        """
        :return Tuple[IcStatistic, Dict[str, IcStatistic]]
        :raises JSONDecodeError: If the response body does not contain valid json
        """
        scigraph = OntologyFactory().create('scigraph:ontology')
        category_stats = {}
        categories = [enum.value for enum in HpoUpperLevel]
        sim_response = self.get_attribute_information_profile(categories=categories)

        try:
            global_stats = IcStatistic(
                mean_mean_ic=float(sim_response['system_stats']['meanMeanIC']),
                mean_sum_ic=float(sim_response['system_stats']['meanSumIC']),
                mean_cls=float(sim_response['system_stats']['meanN']),
                max_max_ic=float(sim_response['system_stats']['maxMaxIC']),
                max_sum_ic=float(sim_response['system_stats']['maxSumIC']),
                individual_count=int(sim_response['system_stats']['individuals']),
                mean_max_ic=float(sim_response['system_stats']['meanMaxIC'])
            )
            for cat_stat in sim_response['categorical_scores']:
                category_stats[cat_stat['id']] = IcStatistic(
                    mean_mean_ic=float(cat_stat['system_stats']['meanMeanIC']),
                    mean_sum_ic=float(cat_stat['system_stats']['meanSumIC']),
                    mean_cls=float(cat_stat['system_stats']['meanN']),
                    max_max_ic=float(cat_stat['system_stats']['maxMaxIC']),
                    max_sum_ic=float(cat_stat['system_stats']['maxSumIC']),
                    individual_count=int(cat_stat['system_stats']['individuals']),
                    mean_max_ic=float(cat_stat['system_stats']['meanMaxIC']),
                    descendants=scigraph.descendants(cat_stat['id'], relations=["subClassOf"])
                )

        except JSONDecodeError as exc_msg:
            raise JSONDecodeError("Cannot parse owlsim2 response: {}".format(exc_msg))

        return global_stats, category_stats

    def __str__(self):
        return "owlsim2 api: {}".format(self.url)
