from ontobio.sim.api.owlsim2 import OwlSim2Api
from ontobio.sim.api.interfaces import SimApi
from typing import Iterable, Dict, Union, Optional, Tuple, List
from ontobio.model.similarity import IcStatistic, AnnotationSufficiency, SimResult, SimMatch, SimQuery, Node
from ontobio.vocabulary.similarity import SimAlgorithm
from ontobio.sim.api.interfaces import FilteredSearchable
from ontobio.golr.golr_associations import get_objects_for_subject
from json.decoder import JSONDecodeError
from ontobio.ontol_factory import OntologyFactory


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
    'MGI': Node(
        id='NCBITaxon:10090',
        label='Mus musculus'
    ),
    'MONDO': Node(
        id='NCBITaxon:9606',
        label='Homo sapiens'
    ),
    'MONARCH': Node(
        id='NCBITaxon:9606',
        label='Homo sapiens'
    ),
    'HGNC': Node(
        id='NCBITaxon:9606',
        label='Homo sapiens'
    ),
    'FlyBase': Node(
        id='NCBITaxon:7227',
        label='Drosophila melanogaster'
    ),
    'WormBase': Node(
        id='NCBITaxon:6239',
        label='Caenorhabditis elegans'
    ),
    'ZFIN': Node(
        id='NCBITaxon:7955',
        label='Danio rerio'
    )
}


class PhenoSimEngine():
    """
    Engine for computing phenotype similarity
    """

    def __init__(self, sim_api: SimApi):
        self.sim_api = sim_api

    def search(
            self,
            id_list: List[str],
            negated_ids: List,
            taxon_filter: Optional[int]=None,
            category_filter: Optional[str]=None,
            method: Union[SimAlgorithm, str, None] = SimAlgorithm.PHENODIGM
    ) -> SimResult:
        """
        Execute a search using owlsim2

        :raises KeyError: If taxon or category is not supported
        :raises NotImplementedError:
            - If sim method is not phenodigm for owlsim2
        :raises ValueError: If id is not supported
        """

        if method not in self.sim_api.matchers():
            raise NotImplementedError("Sim method not implemented "
                                      "in {}".format(str(self.sim_api)))

        namespace_filter = self._get_namespace_filter(taxon_filter, category_filter)

        if namespace_filter is not None\
                and not isinstance(self.sim_api, FilteredSearchable):
            raise NotImplementedError("filtered search not implemented "
                                      "in {}".format(str(self.sim_api)))

        # Determine if entity is a phenotype or individual containing
        # a pheno profile (gene, disease, case, etc)
        pheno_list = []

        node_types = self._get_id_type_map(id_list)

        for node in id_list:
            if 'phenotype' not in node_types[node]:
                pheno_list.append(node)
            else:
                phenotypes = get_objects_for_subject(
                    subject=node, object_category='phenotype', relation='RO:0002200'
                )
                pheno_list = pheno_list + phenotypes

        search_result = self.sim_api.search(
            pheno_list, namespace_filter
        )

        return SimResult(
            query=SimQuery(
                ids=self._get_nodes_from_ids(pheno_list),
                unresolved_ids=[]
            ),
            matches={}
        )

    def compare(self,
                profile_a: Iterable,
                profile_b: Iterable,
                method: SimAlgorithm.PHENODIGM) -> SimResult:
        raise NotImplementedError

    @staticmethod
    def _convert_response_to_match(id_list: List[str]) -> Dict[str, List[str]]:
        pass

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

            for node in PhenoSimEngine._get_scigraph_nodes(**params):
                type_map[node['id']] = [typ.lower() for typ in node['meta']['types']
                                        if typ not in filter_out_types]

        return type_map

    @staticmethod
    def _get_nodes_from_ids(id_list: List[str]) -> List[Node]:
        """
        Given a list of ids return their types

        :param id_list: list of ids
        :return: dictionary where the id is the key and the value is a list of types
        :raises ValueError: If id is not in scigraph
        """
        node_list = []

        chunks = [id_list[i:i + 400] for i in range(0, len(id_list), 400)]
        for chunk in chunks:
            params = {
                'id': chunk,
                'depth': 0
            }

            for result in PhenoSimEngine._get_scigraph_nodes(**params):
                if 'lbl' in result:
                    label = [label for label in result['label'][0]]
                else:
                    label = None # Empty string or None?
                node_list.append(Node(result['id'], label))

        return node_list

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

    @staticmethod
    def _get_namespace_filter(
            taxon_filter: Optional[int]=None,
            category_filter: Optional[str]=None) -> Union[None, str]:
        """
        Given either a taxon and/or category, return the correct namespace
        :raises ValueError: If category is provided without a taxon
        :raises KeyError: If taxon is not supported
        """
        namespace_filter = None
        taxon_category_default = {
            10090: 'gene',
            9606: 'disease',
            7227: 'gene',
            6239: 'gene',
            7955: 'gene'
        }
        if category_filter is not None and taxon_filter is None:
            raise ValueError("Must provide taxon filter along with category")
        elif category_filter is None and taxon_filter is not None:
            category_filter = taxon_category_default[taxon_filter]
        else:
            return namespace_filter

        return TAX_TO_NS[taxon_filter][category_filter.lower()]
