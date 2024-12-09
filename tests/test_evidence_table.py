from pprint import pprint

from ontobio.obograph_util import convert_json_object, obograph_to_assoc_results, convert_json_file
from ontobio.golr.golr_query import GolrAssociationQuery
from unittest.mock import MagicMock

import os
import json
import pysolr


class TestEvidenceTable():
    """
    Functional test for obograph_to_assoc_results
    which converts an evidence graph to an association results object
    """

    @classmethod
    def setup_class(self):
        self.golr_query = GolrAssociationQuery()

        # Mock the PySolr search function to
        # return our test docs
        input_fh = os.path.join(os.path.dirname(__file__),
                                'resources/solr/mock-solr-evidence.json')
        input_docs = json.load(open(input_fh))
        self.pysolr_results = pysolr.Results(input_docs)
        self.golr_query.solr.search = MagicMock(return_value=self.pysolr_results)

    @classmethod
    def teardown_class(self):
        self.manager = None

    def test_obograph_to_assoc_results(self):
        # Hits the mock solr manager in setup_class
        results = self.golr_query.exec()
        assoc = results['associations'][0] if len(results['associations']) > 0 else {}
        eg = {'graphs': [assoc.get('evidence_graph')]}
        digraph = convert_json_object(eg, reverse_edges=False)['graph']
        association_results = obograph_to_assoc_results(digraph)

        results = json.dumps(association_results,
                             default=lambda obj: getattr(obj, '__dict__', str(obj))
        )
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/expected/test-evidence.json')
        expected_results = json.dumps(json.load(open(expected_fh)))

        assert results == expected_results

    def test_obograph_to_digraph_null_properties(self):
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/goslim_generic_missing_components.json')
        with open(expected_fh, 'r') as f:
            json_dict = json.load(f)
        result = convert_json_object(json_dict, reverse_edges=False)
        assert result is not None
        assert result['graph'] is not None


