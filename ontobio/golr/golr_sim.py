"""

Quick similarity calculations

"""

from ontobio.golr.golr_associations import search_associations, GolrFields
import scipy.stats # TODO - move
import scipy as sp # TODO - move

M=GolrFields()  

def get_object_closure(subject, object_category=None, **kwargs):
    """
    Find all terms used to annotate subject plus ancestors
    """
    results = search_associations(subject=subject,
                                  object_category=object_category,
                                  select_fields=[],
                                  facet_fields=[M.OBJECT_CLOSURE],
                                  facet_limit=-1,
                                  rows=0,
                                  **kwargs)
    return set(results['facet_counts'][M.OBJECT_CLOSURE].keys())

def subject_pair_overlap(subject1, subject2, object_category=None, **kwargs):
    """
    Jaccard similarity
    """
    set1 = get_object_closure(subject1,
                              object_category=object_category,
                              **kwargs)
    set2 = get_object_closure(subject2,
                              object_category=object_category,
                              **kwargs)
    return len(set1.intersection(set2)), len(set1.union(set2))

def subject_pair_simj(subject1, subject2, **kwargs):
    """
    Jaccard similarity
    """
    i, u = subject_pair_overlap(subject1, subject2, **kwargs)
    if i==0:
        return 0.0
    return i / u
