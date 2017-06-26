from ontobio.golr.golr_query import GolrSearchQuery

def test_search():
    q = GolrSearchQuery("abnormal")
    print("Q={}".format(q))
    params = q.solr_params()
    print("PARAMS={}".format(params))
    results = q.exec()
    print("RESULTS={}".format(results))
    docs = results['docs']
    for r in docs:
        print(str(r))
    assert len(docs) > 0

def test_cursor():
    """
    Tests rows and start parameters.

    First fetch 100 docs, then same query but iterate with cursor in increments of ten.

    The two sets of IDs returned should be identicial
    """
    q = GolrSearchQuery("abnormal", rows=100)
    results = q.exec()
    docs = results['docs']
    ids = set([d['id'] for d in docs])
    print('Init ids={}'.format(ids))
    assert len(ids) == 100
    matches = set()
    for i in range(0,10):
        q = GolrSearchQuery("abnormal", start=i*10, rows=10)
        docs = q.exec()['docs']
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
    results = q.exec()
    print("RESULTS={}".format(results))
    docs = results['docs']
    for r in docs:
        print(str(r))
    assert len(docs) > 0
    print(str(results['facet_counts']))

def test_search_go_ontol():
    q = GolrSearchQuery("transport*", category='ontology_class', is_go=True)
    print("Q={}".format(q))
    params = q.solr_params()
    print("PARAMS={}".format(params))
    results = q.exec()
    print("RESULTS={}".format(results))
    docs = results['docs']
    for r in docs:
        print(str(r))
    assert len(docs) > 0
    
