from ontobio.golr.golr_query import GolrAssociationQuery
import json
import os
import pysolr
from unittest.mock import MagicMock


def test_clinical_modifiers():
    """
    Test that clinical modifiers show up in the GolrAssociationQuery.exec() object
    when present in the input solr document
    """
    manager = GolrAssociationQuery()
    manager.solr = pysolr.Solr(url="mock_solr", timeout=10)
    input_fh = os.path.join(os.path.dirname(__file__),
                            'resources/solr/input/clinical-mod-doc.json')
    input_docs = json.load(open(input_fh))
    expected_fh = os.path.join(os.path.dirname(__file__),
                               'resources/solr/expected/clinical-mod.json')
    expected_obj = json.load(open(expected_fh))

    manager.solr.search = MagicMock(return_value=pysolr.Results(input_docs))
    results = manager.exec()
    assert json.dumps(expected_obj, sort_keys=True) == \
           json.dumps(results,
                      default=lambda obj: getattr(obj, '__dict__', str(obj)),
                      sort_keys=True)
