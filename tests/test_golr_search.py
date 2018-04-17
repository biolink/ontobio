from ontobio.golr.golr_query import GolrSearchQuery, GolrLayPersonSearch
import pysolr
import os
import json

"""
A group of integration tests, will fail if 
either monarch or go servers are down
"""

def test_search():
    q = GolrSearchQuery("abnormal")
    print("Q={}".format(q))
    params = q.solr_params()
    print("PARAMS={}".format(params))
    results = q.search()
    print("RESULTS={}".format(results))
    docs = results.docs
    for r in docs:
        print(str(r))
    assert len(docs) > 0


def test_cursor():
    """
    Tests rows and start parameters.

    First fetch 100 docs, then same query but iterate with cursor in increments of ten.

    The two sets of IDs returned should be identical
    """
    q = GolrSearchQuery("abnormal", rows=100)
    results = q.search()
    docs = results.docs
    ids = set([d['id'] for d in docs])
    print('Init ids={}'.format(ids))
    assert len(ids) == 100
    matches = set()
    for i in range(0,10):
        q = GolrSearchQuery("abnormal", start=i*10, rows=10)
        docs = q.search().docs
        next_ids = [d['id'] for d in docs]
        assert len(next_ids) == 10
        print('Next ids (from {}) = {}'.format(i*10, next_ids))
        matches.update(next_ids)
    assert len(matches) == 100
    assert len(matches.intersection(ids)) == 100
    

def test_search_go_all():
    q = GolrSearchQuery("transport*", is_go=True)
    print("Q={}".format(q))
    params = q.solr_params()
    print("PARAMS={}".format(params))
    results = q.search()
    print("RESULTS={}".format(results))
    docs = results.docs
    for r in docs:
        print(str(r))
    assert len(docs) > 0
    print(str(results.facet_counts))


def test_search_go_ontol():
    q = GolrSearchQuery("transport*", category='ontology_class', is_go=True)
    print("Q={}".format(q))
    params = q.solr_params()
    print("PARAMS={}".format(params))
    results = q.search()
    print("RESULTS={}".format(results))
    docs = results.docs
    for doc in docs:
        print(str(doc))
    assert len(docs) > 0


def test_lay_doc_conversion():
    """
    Given a sample solr output as a pysolr.Results object
    test that _process_layperson_results returns the
    expected object
    """
    input_fh = os.path.join(os.path.dirname(__file__),
                            'resources/solr/layperson-docs.json')
    expected_fh = os.path.join(os.path.dirname(__file__),
                               'resources/solr/layperson-expected.json')
    golr_layperson = GolrLayPersonSearch()
    input_docs = json.load(open(input_fh))
    processed_docs = json.load(open(expected_fh))
    results = pysolr.Results(input_docs)

    output_docs = golr_layperson._process_layperson_results(results)

    assert json.dumps(processed_docs, sort_keys=True) == json.dumps(output_docs, sort_keys=True)


def test_autocomplete_doc_conversion():
    """
    Given a sample solr output as a pysolr.Results object
    test that _process_autocomplete_results returns the
    expected object
    """
    input_fh = os.path.join(os.path.dirname(__file__),
                            'resources/solr/solr-docs.json')
    expected_fh = os.path.join(os.path.dirname(__file__),
                               'resources/solr/autocomplete-expected.json')
    golr_search = GolrSearchQuery()
    input_docs = json.load(open(input_fh))
    processed_docs = json.load(open(expected_fh))
    results = pysolr.Results(input_docs)

    output_docs = golr_search._process_autocomplete_results(results)

    assert json.dumps(processed_docs, sort_keys=True) == \
           json.dumps(output_docs,
                      default=lambda obj: getattr(obj, '__dict__', str(obj)),
                      sort_keys=True)

def test_search_doc_conversion():
    """
        Given a sample solr output as a pysolr.Results object
        test that _process_autocomplete_results returns the
        expected object
        """
    input_fh = os.path.join(os.path.dirname(__file__),
                            'resources/solr/solr-docs.json')
    expected_fh = os.path.join(os.path.dirname(__file__),
                               'resources/solr/search-expected.json')
    golr_search = GolrSearchQuery()
    input_docs = json.load(open(input_fh))
    processed_docs = json.load(open(expected_fh))
    results = pysolr.Results(input_docs)

    output_docs = golr_search._process_search_results(results)

    assert json.dumps(processed_docs, sort_keys=True) == \
           json.dumps(output_docs,
                      default=lambda obj: getattr(obj, '__dict__', str(obj)),
                      sort_keys=True)
