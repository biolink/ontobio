from ontobio.sim.sim_engine import InformationContentStore, SimilarityEngine
from ontobio.sim.api.owlsim2 import OwlSim2Api
from typing import Iterable, Dict, Union, Optional, Tuple, List
from ontobio.model.similarity import IcStatistic, AnnotationSufficiency, SimResult
from ontobio.config import get_config
from ontobio.vocabulary.similarity import SimAlgorithm
from ontobio.vocabulary.upper import HpoUpperLevel
from json.decoder import JSONDecodeError
from ontobio.ontol_factory import OntologyFactory
import datetime
from cachier import cachier

CONFIG = get_config()

"""
Dictionary that contains taxon to namespace mappings
for owlsim2 which requires namespace for filtering
"""
TAX_TO_NS = {
    10090: {
        'gene': 'MGI'
    },
    9606: {
        'disease': 'MONDO',
        'case': 'MONARCH',
        'gene': 'HGNC'
    },
    7227: {
        'gene': 'FlyBase'
    },
    6239: {
        'gene': 'WormBase'
    },
    7955: {
        'gene': 'ZFIN'
    }
}

# This can be replaced if taxon becomes a node property
NS_TO_TAX = {
    'MGI': 10090,
    'MONDO': 9606,
    'MONARCH': 9606,
    'HGNC': 9606,
    'FlyBase': 7227,
    'WormBase': 6239,
    'ZFIN': 7955
}


class OwlSim2Engine(InformationContentStore, SimilarityEngine):

    def __init__(self, owlsim2: OwlSim2Api):
        self.owlsim2 = owlsim2
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

    def search(
            self,
            nodes: List[str],
            taxon_filter: int,
            category_filter: str,
            method: Union[SimAlgorithm, str, None] = SimAlgorithm.PHENODIGM
    ) -> SimResult:

        # Determine if entity is a phenotype or individual containing
        # a pheno profile (gene, disease, case, etc)
        pheno_list = []

        node_types = self._get_id_type_map(nodes)

        for node in nodes:
            if 'phenotype' not in node_types[node]:
                # enumerate phenotypes
                pass

        if method is not SimAlgorithm.PHENODIGM:
            raise NotImplementedError("Sim method not implemented in owlsim2")
        return

    def compare(self,
                profile_a: Iterable,
                profile_b: Iterable,
                method: SimAlgorithm.PHENODIGM,
                filtr: Optional) -> SimResult:
        raise NotImplementedError

    def get_profile_ic(self, profile: List) -> Dict:
        """
        Given a list of individuals, return their information content
        """
        sim_response = self.owlsim2.get_attribute_information_profile(profile)

        profile_ic = {}
        try:
            for cls in sim_response['input']:
                profile_ic[cls['id']] = cls['IC']
        except JSONDecodeError as exc_msg:
            raise JSONDecodeError("Cannot parse owlsim2 response: {}".format(exc_msg))

        return profile_ic

    def get_annotation_sufficiency(
            self,
            profile: List[str],
            negated_classes: List[str],
            negation_weight: Optional[float] = .25,
            category_weight: Optional[float] = .5) -> AnnotationSufficiency:
        """
        Given a list of individuals, return the annotation sufficiency
        scores

        https://zenodo.org/record/834091#.W8ZnCxhlCV4
        """
        # Simple score is the weighted average of the present and
        # absent phenotypes
        ic_map = self.get_profile_ic(profile + negated_classes)

        # Note that we're deviating from the publication
        # to match the reference java implementation where
        # mean_max_ic is replaced by max_max_ic:
        # https://github.com/owlcollab/owltools/blob/452b4a/
        # OWLTools-Sim/src/main/java/owltools/sim2/AbstractOwlSim.java#L1038
        simple_score = self._get_simple_score(
            profile, negated_classes, self.statistics.mean_mean_ic,
            self.statistics.max_max_ic, self.statistics.mean_sum_ic,
            negation_weight, ic_map
        )

        categories = [enum.value for enum in HpoUpperLevel]
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

    @staticmethod
    def _get_id_type_map(id_list: List[str]) -> Dict[str, List[str]]:
        """
        Given a list of ids return their types

        :param id_list: list of ids
        :return: dictionary where the id is the key and the value is a list of types
        :raises ValueError: If id is not in scigraph
        """
        type_map = {}
        filter_out_types = [
            'cliqueLeader',
            'Class',
            'Node',
            'Individual',
            'quality',
        ]

        chunks = [id_list[i:i + 400] for i in range(0, len(id_list), 400)]
        for chunk in chunks:
            params = {
                'id': chunk,
                'depth': 0
            }

            for node in OwlSim2Engine._get_scigraph_nodes(**params):
                type_map[node['id']] = [typ.lower() for typ in node['meta']['types']
                                        if typ not in filter_out_types]

        return type_map

    @staticmethod
    def _get_id_label_map(id_list: List[str]) -> Dict[str, str]:
        """
        Given a list of ids return their types

        :param id_list: list of ids
        :return: dictionary where the id is the key and the value is a list of types
        :raises ValueError: If id is not in scigraph
        """
        label_map = {}

        chunks = [id_list[i:i + 400] for i in range(0, len(id_list), 400)]
        for chunk in chunks:
            params = {
                'id': chunk,
                'depth': 0
            }

            for node in OwlSim2Engine._get_scigraph_nodes(**params):
                if 'lbl' in node:
                    label_map[node['id']] = [label for label in node['label'][0]]
                else:
                    label_map[node['id']] = "" # Empty string or None?

        return label_map

    @staticmethod
    def _get_scigraph_nodes(**params):
        """
        Generator function for querying scigraph neighbors to get
        a list of nodes back

        We use the scigraph neighbors function because ids can be sent in batch
        which is faster than iteratively querying solr search
        or the scigraph graph/id function

        :return: json decoded result from scigraph_ontology._neighbors_graph
        :raises ValueError: If id is not in scigraph
        """
        scigraph = OntologyFactory().create('scigraph:data')
        try:
            result_graph = scigraph._neighbors_graph(**params)
        except JSONDecodeError as exception:
            # Assume json decode is due to an incorrect class ID
            # Should we handle this?
            raise ValueError(exception.doc)

        yield result_graph['nodes']

    @cachier(datetime.timedelta(days=30))
    def _get_owlsim_stats(self) -> Tuple[IcStatistic, Dict[str, IcStatistic]]:
        """
        :return Tuple[IcStatistic, Dict[str, IcStatistic]]
        :raises JSONDecodeError: If the response body does not contain valid json
        """
        scigraph = OntologyFactory().create('scigraph:ontology')
        category_stats = {}
        categories = [enum.value for enum in HpoUpperLevel]
        sim_response = self.owlsim2.get_attribute_information_profile(categories=categories)

        try:
            global_stats = IcStatistic(
                mean_mean_ic = float(sim_response['system_stats']['meanMeanIC']),
                mean_sum_ic = float(sim_response['system_stats']['meanSumIC']),
                mean_cls = float(sim_response['system_stats']['meanN']),
                max_max_ic = float(sim_response['system_stats']['maxMaxIC']),
                max_sum_ic = float(sim_response['system_stats']['maxSumIC']),
                individual_count = int(sim_response['system_stats']['individuals']),
                mean_max_ic = float(sim_response['system_stats']['meanMaxIC'])
            )
            for cat_stat in sim_response['categorical_scores']:
                category_stats[cat_stat['id']] = IcStatistic(
                    mean_mean_ic = float(cat_stat['system_stats']['meanMeanIC']),
                    mean_sum_ic = float(cat_stat['system_stats']['meanSumIC']),
                    mean_cls = float(cat_stat['system_stats']['meanN']),
                    max_max_ic = float(cat_stat['system_stats']['maxMaxIC']),
                    max_sum_ic = float(cat_stat['system_stats']['maxSumIC']),
                    individual_count = int(cat_stat['system_stats']['individuals']),
                    mean_max_ic = float(cat_stat['system_stats']['meanMaxIC']),
                    descendants = scigraph.descendants(cat_stat['id'], relations=["subClassOf"])
                )

        except JSONDecodeError as exc_msg:
            raise JSONDecodeError("Cannot parse owlsim2 response: {}".format(exc_msg))

        return global_stats, category_stats

