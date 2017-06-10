"""
Convenience wrapper for golr_query.py

In general you should use the `GolrAssociationQuery` object directly. This module provide convenience non-OO functions that typically compose the creation of a GolrAssociationQuery object followed by the `exec` method.

"""
import logging

import pysolr
import json
import logging
import time
from ontobio.golr.golr_query import *

import math ### required for IC calculation

MAX_ROWS = 100000

def get_association(id, **kwargs):
    """
    Fetch an association object by ID
    """
    results = search_associations(id=id, **kwargs)
    return results['associations'][0]

def search_associations(**kwargs):

    """
    Fetch a set of association objects based on a query.
    """
    logging.info("CREATING_GOLR_QUERY {}".format(kwargs))
    q = GolrAssociationQuery(**kwargs)
    return q.exec()

def get_objects_for_subject(subject=None,
                            object_category=None,
                            relation=None,
                            **kwargs):
    """
    Convenience method: Given a subject (e.g. gene, disease, variant), return all associated objects (phenotypes, functions, interacting genes, etc)
    """
    searchresult = search_associations(subject=subject,
                                       fetch_objects=True,
                                       rows=0,
                                       object_category=object_category,
                                       relation=relation,
                                       **kwargs
    )
    objs = searchresult['objects']
    return objs

def get_subjects_for_object(object=None,
                            subject_category=None,
                            subject_taxon=None,
                            relation=None,
                            **kwargs):
    """
    Convenience method: Given a object (e.g. ontology term like phenotype or GO; interacting gene; disease; pathway etc), return all associated subjects (genes, variants, pubs, etc)
    """
    searchresult = search_associations(object=object,
                                       fetch_subjects=True,
                                       rows=0,
                                       subject_category=subject_category,
                                       subject_taxon=subject_taxon,
                                       relation=relation,
                                       **kwargs
    )
    subjs = searchresult['subjects']
    return subjs

def search_associations_compact(**kwargs):
    """
    Convenience method: as for search associations, use compact
    """
    searchresult = search_associations(use_compact_associations=True,
                                       facet_fields=[],
                                       **kwargs
    )
    return searchresult['compact_associations']

def map2slim(subjects, slim, **kwargs):
    """
    Maps a set of subjects (e.g. genes) to a set of slims

    Result is a list of unique subject-class pairs, with
    a list of source assocations
    """
    logging.info("SLIM SUBJECTS:{} SLIM:{} CAT:{}".format(subjects,slim,kwargs.get('category')))
    searchresult = search_associations(subjects=subjects,
                                       slim=slim,
                                       facet_fields=[],
                                       **kwargs
    )
    pmap = {}
    for a in searchresult['associations']:
        subj = a['subject']['id']
        slimmed_terms = a['slim']
        #logging.info('SLIM: {} {}'.format(subj,slimmed_terms))
        for t in slimmed_terms:
            k = (subj,t)
            if k not in pmap:
                pmap[k] = []
            pmap[k].append(a)
    results = [ {'subject': subj, 'slim':t, 'assocs': assocs} for ((subj,t),assocs) in pmap.items()]
    return results

def top_species(**kwargs):
    results = search_associations(facet_fields = [M.SUBJECT_TAXON],
                                  facet=True,
                                  facet_limit=-1,
                                  rows=0,
                                  **kwargs)
    fcs = results['facet_counts']
    logging.info("FCs={}".format(fcs))
    ## TODO:
    if 'taxon' in fcs:
        d = fcs['taxon']
    else:
        d = fcs['subject_taxon']
    return sorted(d.items(), key=lambda t: -t[1])
    


def bulk_fetch(subject_category, object_category, taxon, rows=MAX_ROWS, **kwargs):
    """
    Fetch associations for a species and pair of categories in bulk.

    Arguments:

     - subject_category: String (not None)
     - object_category: String (not None)
     - taxon: String
     - rows: int

    Additionally, any argument for search_associations can be passed
    """
    assert subject_category is not None
    assert object_category is not None
    time.sleep(1)
    logging.info("Bulk query: {} {} {}".format(subject_category, object_category, taxon))
    assocs = search_associations_compact(subject_category=subject_category,
                                         object_category=object_category,
                                         subject_taxon=taxon,
                                         rows=rows,
                                         iterative=True,
                                         **kwargs)
    logging.info("Rows retrieved: {}".format(len(assocs)))
    if len(assocs) == 0:
        logging.error("No associations returned for query: {} {} {}".format(subject_category, object_category, taxon))
    return assocs

def pivot_query(facet=None, facet_pivot_fields=[], **kwargs):
    """
    Pivot query
    """
    results = search_associations(rows=0,
                                  facet_fields=[facet],
                                  #facet_pivot_fields=facet_pivot_fields + [facet],
                                  facet_pivot_fields=facet_pivot_fields,
                                  **kwargs)
    return results

def pivot_query_as_matrix(facet=None, facet_pivot_fields=[], **kwargs):
    """
    Pivot query
    """
    logging.info("Additional args: {}".format(kwargs))
    fp = search_associations(rows=0,
                             facet_fields=[facet],
                             facet_pivot_fields=facet_pivot_fields,
                             **kwargs)['facet_pivot']

    # we assume only one
    results = list(fp.items())[0][1]
    tups = []
    xtype=None
    ytype=None
    xlabels=set()
    ylabels=set()

    
    for r in results:
        logging.info("R={}".format(r))
        xtype=r['field']
        rv = r['value']
        xlabels.add(rv)
        for piv in r['pivot']:
            ytype=piv['field']
            pv = piv['value']
            ylabels.add(pv)
            tups.append( (rv,pv,piv['count']) )

    z = [ [0] * len(xlabels) for i1 in range(len(ylabels)) ]

    xlabels=list(xlabels)
    ylabels=list(ylabels)
    xmap = dict([x[::-1] for x in enumerate(xlabels)])
    ymap = dict([x[::-1] for x in enumerate(ylabels)])
    for t in tups:
        z[ymap[t[1]]][xmap[t[0]]] = t[2]
    m = {'xtype':xtype,
         'ytype':ytype,
         'xaxis':xlabels,
         'yaxis':ylabels,
         'z':z}
    return m
         


# TODO: unify this with the monarch-specific instance
# note that longer term the goal is to unify the go and mon
# golr schemas more. For now the simplest path is
# to introduce this extra method, and 'mimic' the monarch one,
# at the risk of some duplication of code and inelegance

def search_associations_go(
        subject_category=None,
        object_category=None,
        relation=None,
        subject=None,
        **kwargs):
    """
    Perform association search using Monarch golr
    """
    go_golr_url = "http://golr.geneontology.org/solr/"
    go_solr = pysolr.Solr(go_golr_url, timeout=5)
    return search_associations(subject_category,
                               object_category,
                               relation,
                               subject,
                               solr=go_solr,
                               field_mapping=goassoc_fieldmap(),
                               **kwargs)

def select_distinct(distinct_field=None, **kwargs):
    """
    select distinct values for a given field for a given a query
    """
    results = search_associations(rows=0,
                                  select_fields=[],
                                  facet_field_limits = {
                                      distinct_field : -1
                                  },
                                  facet_fields=[distinct_field],
                                  **kwargs
    )
    # TODO: map field
    return list(results['facet_counts'][distinct_field].keys())


def select_distinct_subjects(**kwargs):
    """
    select distinct subject IDs given a query
    """
    return select_distinct(M.SUBJECT, **kwargs)

def calculate_information_content(**kwargs):
    """

    Arguments are as for search_associations, in particular:

     - subject_category
     - object_category
     - subject_taxon

    """
    # TODO - constraint using category and species
    results = search_associations(rows=0,
                                  select_fields=[],
                                  facet_field_limits = {
                                      M.OBJECT : -1
                                  },
                                  facet_fields=[M.OBJECT],
                                  **kwargs
    )
    pop_size = None
    icmap = {}

    # find max
    for (f,fc) in results['facet_counts'][M.OBJECT].items():
        if pop_size is None or pop_size < fc:
            pop_size = fc

    # IC = -Log2(freq)
    for (f,fc) in results['facet_counts'][M.OBJECT].items():
        freq = fc/pop_size
        icmap[f] = -math.log(freq, 2)
    return icmap
