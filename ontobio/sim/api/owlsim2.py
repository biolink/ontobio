from ontobio.config import get_config
from typing import List, Optional, Dict
import requests


class OwlSim2Api():
    """
    Owlsim2 is part of the owltools package and uses a modified
    version of the phenodigm algorithm to compute semantic similarity,
    using IC instead of the geometric mean of IC and jaccard similarities

    refs: https://github.com/owlcollab/owltools/tree/master/OWLTools-Sim
          https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3649640/

    The monarch instance computes similarity over phenotype profiles,
    so this API refers to phenotypes as input and phenotypic similarity
    """

    def __init__(self, url: Optional[str]=None, timeout: Optional[int]=None):
        self.url = url if url is not None else get_config().owlsim2.url
        self.timeout = timeout if timeout is not None else get_config().owlsim2.timeout

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
