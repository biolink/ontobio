from ontobio.sim.phenosim_engine import PhenoSimEngine
from ontobio.sim.api.owlsim2 import OwlSim2Api
from ontobio.model.similarity import Node, TypedNode

from unittest.mock import MagicMock, patch
import os
import json


def mock_resolve_nodes(id_list):
    """
    Mock phenosim_engine _resolve_nodes_to_phenotypes
    """
    if id_list == ['HP:0002367', 'HP:0031466', 'HP:0007123']:
        ret_val = id_list
    elif id_list == ['MONDO:0008199']:
        ret_val = ['HP:0000751', 'HP:0000738', 'HP:0000726']
    return ret_val


def mock_get_id_type_map(id_list):
    """
    Mock scigraph_util get_id_type_map
    """
    if id_list == ['OMIM:611203', 'MONDO:0008083']:
        ret_val = {'MONDO:0008083': ['disease'], 'OMIM:611203': ['gene']}
    elif id_list == ['MONDO:0008199']:
        ret_val = ['HP:0000751', 'HP:0000738', 'HP:0000726']
    return ret_val


def mock_get_nodes_from_ids(id_list):
    """
    Mock scigraph_util get_nodes_from_ids
    """
    test_set_a = [
        'http://purl.obolibrary.org/obo/HP_0002367',
        'http://purl.obolibrary.org/obo/HP_0007123',
        'http://purl.obolibrary.org/obo/HP_0031466'
    ]

    test_set_b = [
        'http://purl.obolibrary.org/obo/HP_0000751',
        'http://purl.obolibrary.org/obo/HP_0000738',
        'http://purl.obolibrary.org/obo/HP_0000726'
    ]
    if id_list == test_set_a:
        ret_val = [
            Node(id="HP:0031466", label="Impairment in personality functioning"),
            Node(id="HP:0002367", label="Visual hallucinations"),
            Node(id="HP:0007123", label="Subcortical dementia")
        ]
    elif id_list == test_set_b:
        ret_val = [
            Node(id="HP:0000751", label="Personality changes"),
            Node(id="HP:0000726", label="Dementia"),
            Node(id="HP:0000738", label="Hallucinations")
        ]
    return ret_val


def mock_typed_node_from_id(test_id):
    """
    Mock scigraph_util typed_node_from_id
    """
    if test_id == "MONDO:0008199":
        ret_val = TypedNode(
            id="MONDO:0008199",
            label="Parkinson disease, late-onset",
            type="disease",
            taxon=Node(
                id="NCBITaxon:9606",
                label="Homo sapiens"
            )
        )
    return ret_val


class TestPhenoSimEngine():
    """
    Functional test of ontobio.sim.phenosim_engine.PhenoSimEngine
    using mock return values from owlsim2, scigraph, and solr assocs
    """

    @classmethod
    @patch.object(OwlSim2Api, '_get_owlsim_stats',  MagicMock(return_value=(None, None)))
    def setup_class(self):

        self.resolve_mock = patch.object(PhenoSimEngine, '_resolve_nodes_to_phenotypes',
                                         side_effect=mock_resolve_nodes)
        self.mock_get_nodes = patch('ontobio.sim.api.owlsim2.get_nodes_from_ids',
                                    side_effect=mock_get_nodes_from_ids)
        self.mock_get_id_type = patch('ontobio.sim.api.owlsim2.get_id_type_map',
                                      side_effect=mock_get_id_type_map)
        self.mock_typed_node = patch('ontobio.sim.phenosim_engine.typed_node_from_id',
                                     side_effect=mock_typed_node_from_id)

        self.owlsim2_api = OwlSim2Api()
        self.pheno_sim = PhenoSimEngine(self.owlsim2_api)

        self.resolve_mock.start()
        self.mock_get_nodes.start()
        self.mock_get_id_type.start()
        self.mock_typed_node.start()

    @classmethod
    def teardown_class(self):
        self.owlsim2_api = None
        self.pheno_sim = None
        self.resolve_mock.stop()
        self.mock_get_nodes.stop()
        self.mock_get_id_type.stop()
        self.mock_typed_node.stop()

    def test_sim_search(self):
        # Load fake output from owlsim2 and mock search_by_attribute_set
        mock_search_fh = os.path.join(os.path.dirname(__file__),
                                      'resources/owlsim2/mock-owlsim-search.json')
        mock_search = json.load(open(mock_search_fh))
        self.owlsim2_api.search_by_attribute_set = MagicMock(return_value=mock_search)

        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/owlsim2/mock-sim-search.json')

        expected_sim_results = json.load(open(expected_fh))

        classes = ['HP:0002367', 'HP:0031466', 'HP:0007123']
        search_results = self.pheno_sim.search(classes)

        results = json.loads(
            json.dumps(search_results,
                       default=lambda obj: getattr(obj, '__dict__', str(obj))
                       )
        )
        assert expected_sim_results == results


    def test_sim_compare(self):
        # Load fake output from owlsim2 and mock compare
        mock_search_fh = os.path.join(os.path.dirname(__file__),
                                      'resources/owlsim2/mock-owlsim-compare.json')
        mock_compare = json.load(open(mock_search_fh))
        self.owlsim2_api.compare_attribute_sets = MagicMock(return_value=mock_compare)

        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/owlsim2/mock-sim-compare.json')

        expected_sim_results = json.load(open(expected_fh))

        individuals_a = ['MONDO:0008199']
        individuals_b = [['HP:0002367', 'HP:0031466', 'HP:0007123']]
        compare_results = self.pheno_sim.compare(individuals_a, individuals_b)

        results = json.loads(
            json.dumps(compare_results,
                       default=lambda obj: getattr(obj, '__dict__', str(obj))
                       )
        )
        assert expected_sim_results == results
