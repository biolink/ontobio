"""

Experimental enrichment implemented over solr.

Currently the strategy implemented here does not scale due to the need for large OR clauses (alternatively: iterative queries)

The most efficient strategy may be to pre-load associations and compute in-memory

"""

from ontobio.golr.golr_associations import search_associations, GolrFields
import scipy.stats # TODO - move
import scipy as sp # TODO - move

M=GolrFields()  

def get_counts(entities=None,
               object_category=None,
               min_count=1,
               **kwargs):
    """
    given a set of entities (genes, diseases, etc), finds the number of entities associated with each descriptor in a given category.

    The result is a tuple (cmap, results), where cmap is a dict of TERM:COUNT

    """
    if entities is None:
        entities = []
    results = search_associations(subjects=entities,
                                  subject_direct=True,
                                  rows=0,
                                  facet_fields=[M.IS_DEFINED_BY, M.SUBJECT_TAXON, M.SUBJECT_CATEGORY],
                                  object_category=object_category,
                                  facet_mincount=3, # TODO
                                  facet_limit=-1,
                                  json_facet={
                                      'categories':{
                                          'limit':-1,
                                          'type': 'terms',
                                          'field' : M.OBJECT_CLOSURE,
                                          'facet' : {
                                              'uniq_subject': "unique(subject)"
                                          }
                                      }
                                  },
                                  **kwargs)
    buckets = results['facets']['categories']['buckets']
    cmap = {}
    for bucket in buckets:
        if bucket['uniq_subject'] >= min_count:
            cmap[bucket['val']] = bucket['uniq_subject']
    return (cmap, results)

def get_background(objects, taxon, object_category, **kwargs):
    results = search_associations(objects=objects,
                                  subject_taxon=taxon,
                                  object_category=object_category,
                                  rows=0,
                                  facet_fields=[M.SUBJECT],
                                  facet_mincount=3, # TODO
                                  facet_limit=-1,
                                  **kwargs)
    return results['facet_counts'][M.SUBJECT].keys()

# TODO: refactor this - fetch compact associations
def find_enriched(sample_entities=None,
                  background_entities=None,
                  object_category=None,
                  **kwargs):

    """
    Given a sample set of sample_entities (e.g. overexpressed genes) and a background set (e.g. all genes assayed), and a category of descriptor (e.g. phenotype, function),
    return enriched descriptors/classes
    """
    if sample_entities is None:
        sample_entites = []

    (sample_counts, sample_results) = get_counts(entities=sample_entities,
                                                 object_category=object_category,
                                                 min_count=2,
                                                 **kwargs)
    print(str(sample_counts))

    sample_fcs = sample_results['facet_counts']
    taxon_count_dict = sample_fcs[M.SUBJECT_TAXON]

    taxon=None
    for (t,tc) in taxon_count_dict.items():
        # TODO - throw error if multiple taxa
        taxon = t

    if background_entities is None:
        objects = list(sample_counts.keys())
        print("OBJECTS="+str(objects))
        background_entities = get_background(objects, taxon, object_category)

    # TODO: consider caching
    (bg_counts,_) = get_counts(entities=background_entities,
                               object_category=object_category,
                               **kwargs)

    sample_n = len(sample_entities) # TODO - annotated only?
    pop_n = len(background_entities)
    # adapted from goatools
    for (sample_termid,sample_count) in sample_counts.items():
        pop_count = bg_counts[sample_termid]

        # https://en.wikipedia.org/wiki/Fisher's_exact_test
        #              Cls  NotCls
        # study/sample [a,      b]
        # rest of ref  [c,      d]
        #              
        a = sample_count
        b = sample_n - sample_count
        c = pop_count - sample_count
        d = pop_n - pop_count - b
        print("ABCD="+str((sample_termid,a,b,c,d,sample_n)))
        _, p_uncorrected = sp.stats.fisher_exact( [[a, b], [c, d]])
        print("P="+str(p_uncorrected))
        # TODO: construct into object
