from ontobio.sim.phenosim_engine import PhenoSimEngine
from ontobio.sim.api.owlsim2 import OwlSim2Api

from unittest.mock import MagicMock, patch
import os
import json


def mock_resolve_nodes(id_list):
    """
    Mock phenosim_engine _resolve_nodes_to_phenotypes
    Replaces calls to scigraph and solr
    """
    if id_list == ['HP:0002367', 'HP:0031466', 'HP:0007123']:
        ret_val = id_list
    elif id_list == ['MONDO:0008199']:
        ret_val = ['HP:0000751', 'HP:0000738', 'HP:0000726']
    return ret_val


def mock_get_scigraph_nodes(id_list):
    """
    Mock scigraph_util get_scigraph_nodes
    """
    scigraph_desc_fh = os.path.join(os.path.dirname(__file__),
                                    'resources/owlsim2/mock-scigraph-nodes.json')
    ids = [iri.replace("http://purl.obolibrary.org/obo/HP_", "HP:") for iri in id_list]
    scigraph_res = json.load(open(scigraph_desc_fh))
    for node in scigraph_res['nodes']:
        if node['id'] in ids:
            yield node


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
        self.mock_scigraph = patch('ontobio.util.scigraph_util.get_scigraph_nodes',
                                   side_effect=mock_get_scigraph_nodes)

        self.owlsim2_api = OwlSim2Api()
        self.pheno_sim = PhenoSimEngine(self.owlsim2_api)

        self.resolve_mock.start()
        self.mock_scigraph.start()

    @classmethod
    def teardown_class(self):
        self.owlsim2_api = None
        self.pheno_sim = None
        self.resolve_mock.stop()
        self.mock_scigraph.stop()

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
