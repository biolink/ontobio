"""

Experimental enrichment implemented over solr.

Currently the strategy implemented here does not scale due to the need for large OR clauses (alternatively: iterative queries)

The most efficient strategy may be to pre-load associations and compute in-memory

"""

from ontobio.golr.golr_associations import search_associations, GolrFields
import scipy.stats # TODO - move
import scipy as sp # TODO - move

M=GolrFields()

def term_matrix(idlist, subject_category, taxon, **kwargs):
    """
    Intersection between annotated objects

             P1  not(P1)
    F1       0   5
    not(F1)  6   0
    """
    results = search_associations(objects=idlist,
                                  subject_taxon=taxon,
                                  subject_category=subject_category,
                                  select_fields=[M.SUBJECT, M.OBJECT_CLOSURE],
                                  facet_fields=[],
                                  rows=-1,
                                  include_raw=True,
                                  **kwargs)
    docs = results['raw'].docs

    subjects_per_term = {}
    smap = {}
    for d in docs:
        smap[d[M.SUBJECT]] = 1
        for c in d[M.OBJECT_CLOSURE]:
            if c in idlist:
                if c not in subjects_per_term:
                    subjects_per_term[c] = []
                subjects_per_term[c].append(d[M.SUBJECT])
    pop_n = len(smap.keys())

    cells = []
    for cx in idlist:
        csubjs = set(subjects_per_term[cx])
        for dx in idlist:
            dsubjs = set(subjects_per_term[dx])
            a = len(csubjs.intersection(dsubjs))
            b = len(csubjs) - a
            c = len(dsubjs) - a
            d = pop_n - len(dsubjs) - b
            ctable = [[a, b], [c, d]]

            _, p_under = sp.stats.fisher_exact(ctable, 'less')
            _, p_over = sp.stats.fisher_exact(ctable, 'greater')

            cells.append({'c':cx, 'd':dx,
                          'nc':len(csubjs),
                          'nd':len(dsubjs),
                          'n':a,
                          'p_l':p_under,
                          'p_g':p_over
            })
    return cells
