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
    
