"""Wrapper for a Solr index following Golr conventions

Intended to work with:

 * Monarch golr instance
 * AmiGO/GO golr instance

# Conventions

Documents follow either entity or association patterns.

## Associations

Connects some kind of *subject* to an *object* via a *relation*, this
should be read as any RDF triple.

The subject may be a molecular biological entity such as a gene, or an
ontology class. The distinction between these two may be malleable.

The object is typically an ontology class, but not
always. E.g. gene-gene interactions or homology for exceptions.

An association also has evidence plus various provenance metadata.

In Monarch, the evidence is modeled as a graph encoded as a JSON blob;

In AmiGO, we follow the GAF data model where it is assumed evidence is
simple as does not follow chains, there is assumed to be one evidence
object for the intermediate entity.

### Entities

TODO

"""
import logging

import pysolr
import json
import logging
import time

import math ### TODO - move?

MAX_ROWS=100000

class GolrFields:
    """
    Enumeration of fields in Golr.
    Note the Monarch golr schema is taken as canonical here
    """

    ID='id'
    SOURCE='source'
    OBJECT_CLOSURE='object_closure'
    SOURCE_CLOSURE_MAP='source_closure_map'
    SUBJECT_TAXON_CLOSURE_LABEL='subject_taxon_closure_label'
    SUBJECT_GENE_CLOSURE_MAP='subject_gene_closure_map'
    EVIDENCE_OBJECT='evidence_object'
    SUBJECT_TAXON_LABEL_SEARCHABLE='subject_taxon_label_searchable'
    IS_DEFINED_BY='is_defined_by'
    SUBJECT_GENE_CLOSURE_LABEL='subject_gene_closure_label'
    EVIDENCE_OBJECT_CLOSURE_LABEL='evidence_object_closure_label'
    SUBJECT_TAXON_CLOSURE='subject_taxon_closure'
    OBJECT_LABEL='object_label'
    SUBJECT_CATEGORY='subject_category'
    SUBJECT_GENE_LABEL='subject_gene_label'
    SUBJECT_TAXON_CLOSURE_LABEL_SEARCHABLE='subject_taxon_closure_label_searchable'
    SUBJECT_GENE_CLOSURE='subject_gene_closure'
    SUBJECT_GENE_LABEL_SEARCHABLE='subject_gene_label_searchable'
    SUBJECT='subject'
    SUBJECT_LABEL='subject_label'
    SUBJECT_CLOSURE_LABEL_SEARCHABLE='subject_closure_label_searchable'
    OBJECT_CLOSURE_LABEL_SEARCHABLE='object_closure_label_searchable'
    EVIDENCE_OBJECT_CLOSURE='evidence_object_closure'
    OBJECT_CLOSURE_LABEL='object_closure_label'
    EVIDENCE_CLOSURE_MAP='evidence_closure_map'
    SUBJECT_CLOSURE_LABEL='subject_closure_label'
    SUBJECT_GENE='subject_gene'
    SUBJECT_TAXON='subject_taxon'
    OBJECT_LABEL_SEARCHABLE='object_label_searchable'
    OBJECT_CATEGORY='object_category'
    SUBJECT_TAXON_CLOSURE_MAP='subject_taxon_closure_map'
    QUALIFIER='qualifier'
    SUBJECT_TAXON_LABEL='subject_taxon_label'
    SUBJECT_CLOSURE_MAP='subject_closure_map'
    SUBJECT_ORTHOLOG_CLOSURE='subject_ortholog_closure'
    EVIDENCE_GRAPH='evidence_graph'
    SUBJECT_CLOSURE='subject_closure'
    OBJECT='object'
    OBJECT_CLOSURE_MAP='object_closure_map'
    SUBJECT_LABEL_SEARCHABLE='subject_label_searchable'
    EVIDENCE_OBJECT_CLOSURE_MAP='evidence_object_closure_map'
    EVIDENCE_OBJECT_LABEL='evidence_object_label'
    _VERSION_='_version_'
    SUBJECT_GENE_CLOSURE_LABEL_SEARCHABLE='subject_gene_closure_label_searchable'

    RELATION='relation'
    RELATION_LABEL='relation_label'

    # golr convention: for any entity FOO, the id is denoted 'foo'
    # and the label FOO_label
    def label_field(self, f):
        return f + "_label"

    # golr convention: for any class FOO, the id is denoted 'foo'
    # and the cosure FOO_closure. Other closures may exist
    def closure_field(self, f):
        return f + "_closure"

# create an instance
M=GolrFields()

# normalize to what Monarch uses
PREFIX_NORMALIZATION_MAP = {
    'MGI:MGI' : 'MGI',
    'FB' : 'FlyBase'
}

def make_canonical_identifier(id):
    if id is not None:
        for (k,v) in PREFIX_NORMALIZATION_MAP.items():
            s = k+':'
            if id.startswith(s):
                return id.replace(s,v+':')
    return id

def make_gostyle_identifier(id):
    if id is not None:
        for (k,v) in PREFIX_NORMALIZATION_MAP.items():
            s = v+':'
            if id.startswith(s):
                return id.replace(s,k+':')
    return id

# We take the monarch golr as default
# TODO: config
monarch_golr_url = "https://solr.monarchinitiative.org/solr/golr/"
monarch_solr = pysolr.Solr(monarch_golr_url, timeout=5)

def translate_objs(d,fname):
    """
    Translate a field whose value is expected to be a list
    """
    if fname not in d:
        # TODO: consider adding arg for failure on null
        return None

    #lf = M.label_field(fname)

    v = d[fname]
    if not isinstance(v,list):
        v = [v]
    objs = [{'id': idval} for idval in v]
    # todo - labels

    return objs


def translate_obj(d,fname):
    """
    Translate a field value from a solr document.

    This includes special logic for when the field value
    denotes an object, here we nest it
    """
    if fname not in d:
        # TODO: consider adding arg for failure on null
        return None

    lf = M.label_field(fname)

    id = d[fname]
    id = make_canonical_identifier(id)
    #if id.startswith('MGI:MGI:'):
    #    id = id.replace('MGI:MGI:','MGI:')
    obj = {'id': id}

    if lf in d:
        obj['label'] = d[lf]

    cf = fname + "_category"
    if cf in d:
        obj['categories'] = [d[cf]]

    return obj

def map_doc(d, field_mapping):
    for (k,v) in field_mapping.items():
        if v is not None and k is not None:
            #logging.debug("TESTING FOR:"+v+" IN "+str(d))
            if v in d:
                #logging.debug("Setting field {} to {} // was in {}".format(k,d[v],v))
                d[k] = d[v]
    return d

def translate_doc(d, field_mapping=None, map_identifiers=None, **kwargs):
    """
    Translate a solr document (i.e. a single result row)
    """
    if field_mapping is not None:
        map_doc(d, field_mapping)
    subject = translate_obj(d,M.SUBJECT)


    # TODO: use a more robust method; we need equivalence as separate field in solr
    if map_identifiers is not None:
        if M.SUBJECT_CLOSURE in d:
            subject['id'] = map_id(subject, map_identifiers, d[M.SUBJECT_CLOSURE])
        else:
            logging.info("NO SUBJECT CLOSURE IN: "+str(d))

    if M.SUBJECT_TAXON in d:
        subject['taxon'] = translate_obj(d,M.SUBJECT_TAXON)
    assoc = {'id':d.get(M.ID),
             'subject': subject,
             'object': translate_obj(d,'object'),
             'relation': translate_obj(d,M.RELATION),
             'publications': translate_objs(d,M.SOURCE),  # note 'source' is used in the golr schema
    }
    if M.OBJECT_CLOSURE in d:
        assoc['object_closure'] = d.get(M.OBJECT_CLOSURE)
    if M.IS_DEFINED_BY in d:
        if isinstance(d[M.IS_DEFINED_BY],list):
            assoc['provided_by'] = d[M.IS_DEFINED_BY]
        else:
            # hack for GO Golr instance
            assoc['provided_by'] = [d[M.IS_DEFINED_BY]]
    if M.EVIDENCE_OBJECT in d:
        assoc['evidence'] = d[M.EVIDENCE_OBJECT]
    # solr does not allow nested objects, so evidence graph is json-encoded
    if M.EVIDENCE_GRAPH in d:
        assoc[M.EVIDENCE_GRAPH] = json.loads(d[M.EVIDENCE_GRAPH])
    return assoc

def translate_docs(ds, **kwargs):
    """
    Translate a set of solr results
    """
    return [translate_doc(d, **kwargs) for d in ds]


def translate_docs_compact(ds, field_mapping=None, slim=None, map_identifiers=None, **kwargs):
    """
    Translate golr association documents to a compact representation
    """
    amap = {}
    logging.info("Translating docs to compact form. Slim={}".format(slim))
    for d in ds:
        if field_mapping is not None:
            map_doc(d, field_mapping)

        subject = d[M.SUBJECT]
        subject_label = d[M.SUBJECT_LABEL]

        # TODO: use a more robust method; we need equivalence as separate field in solr
        if map_identifiers is not None:
            if M.SUBJECT_CLOSURE in d:
                subject = map_id(subject, map_identifiers, d[M.SUBJECT_CLOSURE])
            else:
                logging.debug("NO SUBJECT CLOSURE IN: "+str(d))

        rel = d.get(M.RELATION)
        skip = False

        # TODO
        if rel == 'not' or rel == 'NOT':
            skip = True

        # this is a list in GO
        if isinstance(rel,list):
            if 'not' in rel or 'NOT' in rel:
                skip = True
            if len(rel) > 1:
                logging.warn(">1 relation: {}".format(rel))
            rel = ";".join(rel)

        if skip:
            logging.debug("Skipping: {}".format(d))
            continue

        subject = make_canonical_identifier(subject)
        #if subject.startswith('MGI:MGI:'):
        #    subject = subject.replace('MGI:MGI:','MGI:')

        k = (subject,rel)
        if k not in amap:
            amap[k] = {'subject':subject,
                       'subject_label':subject_label,
                       'relation':rel,
                       'objects': []}
        if slim is not None and len(slim)>0:
            mapped_objects = [x for x in d[M.OBJECT_CLOSURE] if x in slim]
            logging.debug("Mapped objects: {}".format(mapped_objects))
            amap[k]['objects'] += mapped_objects
        else:
            amap[k]['objects'].append(d[M.OBJECT])
    for k in amap.keys():
        amap[k]['objects'] = list(set(amap[k]['objects']))

    return list(amap.values())

def map_id(id, prefix, closure_list):
    """
    Map identifiers based on an equivalence closure list.
    """
    prefixc = prefix + ':'
    ids = [eid for eid in closure_list if eid.startswith(prefixc)]
    # TODO: add option to fail if no mapping, or if >1 mapping
    if len(ids) == 0:
        # default to input
        return id
    return ids[0]

def get_association(id, **kwargs):
    """
    Fetch an association object by ID
    """
    results = search_associations(id=id, **kwargs)
    return results['associations'][0]

def search_associations(subject_category=None,
                        object_category=None,
                        relation=None,
                        subject=None,
                        subjects=None,
                        object=None,
                        objects=None,
                        subject_direct=False,
                        subject_taxon=None,
                        object_taxon=None,
                        invert_subject_object=False,
                        use_compact_associations=False,
                        include_raw=False,
                        field_mapping=None,
                        solr=monarch_solr,
                        select_fields=None,
                        fetch_objects=False,
                        fetch_subjects=False,
                        slim=[],
                        json_facet=None,
                        iterate=False,
                        map_identifiers=None,
                        facet_fields = [
                            M.SUBJECT_TAXON_LABEL,
                            M.OBJECT_CLOSURE
                        ],
                        facet_field_limits = None,
                        facet_limit=25,
                        facet_mincount=1,
                        facet_pivot_fields = [],
                        facet_on = 'on',
                        rows=10,
                        **kwargs):

    """Fetch a set of association objects based on a query.

    Arguments
    ---------

    fetch_objects : bool

        we frequently want a list of distinct association objects (in
        the RDF sense).  for example, when querying for all phenotype
        associations for a gene, it is convenient to get a list of
        distinct phenotype terms. Although this can be obtained by
        iterating over the list of associations, it can be expensive
        to obtain all associations.

        Results are in the 'objects' field

    fetch_subjects : bool

        This is the analog of the fetch_objects field. Note that due
        to an inherent asymmetry by which the list of subjects can be
        very large (e.g. all genes in all species for "metabolic
        process" or "metabolic phenotype") it's necessary to combine
        this with subject_category and subject_taxon filters

        Results are in the 'subjects' field

    slim : List

        a list of either class ids (or in future subset ids), used to
        map up (slim) objects in associations. This will populate
        an additional 'slim' field in each association object corresponding
        to the slimmed-up value(s) from the direct objects.
        If fetch_objects is passed, this will be populated with slimmed IDs.

    exclude_automatic_annotations : bool

        If true, then any annotations with evidence of ECO:0000501 or
        subclasses will be excluded.

    use_compact_associations : bool

        If true, then the associations list will be false, instead
        compact_associations contains a more compact representation
        consisting of objects with (subject, relation and objects)

    """
    fq = {}

    # canonical form for MGI is a CURIE MGI:nnnn
    #if subject is not None and subject.startswith('MGI:MGI:'):
    #    logging.info('Unhacking MGI ID presumably from GO:'+str(subject))
    #    subject = subject.replace("MGI:MGI:","MGI")
    if subject is not None:
        subject = make_canonical_identifier(subject)
    if subjects is not None:
        subjects = [make_canonical_identifier(s) for s in subjects]

    # temporary: for querying go solr, map fields. TODO
    logging.info("Object category: {}".format(object_category))
    if object_category is None and object is not None and object.startswith('GO:'):
        object_category = 'function'
        logging.info("Inferring Object category: {}".format(object_category))
        
    if object_category is not None and object_category == 'function':
        go_golr_url = "http://golr.berkeleybop.org/solr/"
        solr = pysolr.Solr(go_golr_url, timeout=5)
        field_mapping=goassoc_fieldmap()
        fq['document_category'] = 'annotation'
        if subject is not None:
            subject = make_gostyle_identifier(subject)
        if subjects is not None:
            subjects = [make_gostyle_identifier(s) for s in subjects]

    # typically information is stored one-way, e.g. model-disease;
    # sometimes we want associations from perspective of object
    if invert_subject_object:
        (subject,object) = (object,subject)
        (subject_category,object_category) = (object_category,subject_category)
        (subject_taxon,object_taxon) = (object_taxon,subject_taxon)

    if use_compact_associations:
        facet_fields = []
        facet_on = 'off'
        facet_limit = 0
        select_fields = [
            M.SUBJECT,
            M.SUBJECT_LABEL,
            M.RELATION,
            M.OBJECT]

    if subject_category is not None:
        fq['subject_category'] = subject_category
    if object_category is not None:
        fq['object_category'] = object_category


    if object is not None:
        # TODO: make configurable whether to use closure
        fq['object_closure'] = object
    if subject is not None:
        # note: by including subject closure by default,
        # we automaticaly get equivalent nodes
        if subject_direct:
            fq['subject'] = subject
        else:
            fq['subject_closure'] = subject
    if subjects is not None:
        # lists are assumed to be disjunctive
        if subject_direct:
            fq['subject'] = subjects
        else:
            fq['subject_closure'] = subjects
    if objects is not None:
        # lists are assumed to be disjunctive
        fq['object_closure'] = objects
    if relation is not None:
        fq['relation_closure'] = relation
    if subject_taxon is not None:
        fq['subject_taxon_closure'] = subject_taxon
    if 'id' in kwargs:
        fq['id'] = kwargs['id']
    if 'evidence' in kwargs and kwargs['evidence'] is not None:
        fq['evidence_object_closure'] = kwargs['evidence']
    if 'exclude_automatic_assertions' in kwargs and kwargs['exclude_automatic_assertions']:
        fq['-evidence_object_closure'] = 'ECO:0000501'
    if 'pivot_subject_object' in kwargs and kwargs['pivot_subject_object']:
        facet_pivot_fields = [M.SUBJECT, M.OBJECT]


    # Map solr field names for fq. The generic Monarch schema is
    # canonical, GO schema is mapped to this using
    # field_mapping dictionary
    if field_mapping is not None:
        for (k,v) in field_mapping.items():

            # map fq[k] -> fq[k]
            if k in fq:
                if v is None:
                    del fq[k]
                else:
                    fq[v] = fq[k]
                    del fq[k]

            # in solr, the fq field can be
            # a negated expression, e.g. -evidence_object_closure:"ECO:0000501"
            # ideally we would have a higher level representation rather than
            # relying on string munging...
            negk = '-' + k
            if negk in fq:
                if v is None:
                    del fq[negk]
                else:
                    negv = '-' + v
                    fq[negv] = fq[negk]
                    del fq[negk]

    filter_queries = []
    qstr = "*:*"
    filter_queries = [ '{}:{}'.format(k,solr_quotify(v)) for (k,v) in fq.items()]

    # unless caller specifies a field list, use default
    if select_fields is None:
        select_fields = [
            M.ID,
            M.IS_DEFINED_BY,
            M.SOURCE,
            M.SUBJECT,
            M.SUBJECT_LABEL,
            M.SUBJECT_TAXON,
            M.SUBJECT_TAXON_LABEL,
            M.RELATION,
            M.RELATION_LABEL,
            M.OBJECT,
            M.OBJECT_LABEL,
        ]
        if 'unselect_evidence' not in kwargs or not kwargs['unselect_evidence']:
            select_fields += [
                M.EVIDENCE_OBJECT,
                M.EVIDENCE_GRAPH
            ]

    if map_identifiers is not None:
        select_fields.append(M.SUBJECT_CLOSURE)

    if slim is not None and len(slim)>0:
        select_fields.append(M.OBJECT_CLOSURE)

    if field_mapping is not None:
        logging.info("Applying field mapping to SELECT: {}".format(field_mapping))
        select_fields = [ map_field(fn, field_mapping) for fn in select_fields ]


    facet_fields = [ map_field(fn, field_mapping) for fn in facet_fields ]

    #logging.info('FL'+str(select_fields))
    is_unlimited = False
    if rows < 0:
        is_unlimited = True
        iterate = True
        rows = MAX_ROWS
    params = {
        'q': qstr,
        'fq': filter_queries,
        'facet': facet_on,
        'facet.field': facet_fields,
        'facet.limit': facet_limit,
        'facet.mincount': facet_mincount,
        'fl': ",".join(select_fields),
        'rows': rows
    }
    if json_facet:
        params['json.facet'] = json.dumps(json_facet)

    if facet_field_limits is not None:
        for (f,flim) in facet_field_limits.items():
            params["f."+f+".facet.limit"] = flim


    if len(facet_pivot_fields) > 0:
        params['facet.pivot'] = ",".join(facet_pivot_fields)
        params['facet.pivot.mincount'] = 1

    logging.info("PARAMS="+str(params))
    results = solr.search(**params)
    n_docs = len(results.docs)
    logging.info("Docs found: {}".format(results.hits))

    if iterate:
        docs = results.docs
        start = n_docs
        while n_docs >= rows:
            logging.info("Iterating; start={}".format(start))
            next_results = solr.search(**params, start=start)
            next_docs = next_results.docs
            n_docs = len(next_docs)
            docs += next_docs
            start += rows
        results.docs = docs



    fcs = results.facets

    payload = {
        'facet_counts': translate_facet_field(fcs),
        'pagination': {}
    }

    if include_raw:
        # note: this is not JSON serializable, do not send via REST
        payload['raw'] = results

    # TODO - check if truncated

    logging.info("COMPACT="+str(use_compact_associations))
    if use_compact_associations:
        payload['compact_associations'] = translate_docs_compact(results.docs, field_mapping=field_mapping, slim=slim, map_identifiers=map_identifiers, **kwargs)
    else:
        payload['associations'] = translate_docs(results.docs, field_mapping=field_mapping, map_identifiers=map_identifiers, **kwargs)

    if 'facet_pivot' in fcs:
        payload['facet_pivot'] = fcs['facet_pivot']
    if 'facets' in results.raw_response:
        payload['facets'] = results.raw_response['facets']

    # For solr, we implement this by finding all facets
    # TODO: no need to do 2nd query, see https://wiki.apache.org/solr/SimpleFacetParameters#Parameters
    if fetch_objects:
        core_object_field = M.OBJECT
        if slim is not None and len(slim)>0:
            core_object_field = M.OBJECT_CLOSURE
        object_field = map_field(core_object_field, field_mapping)
        if invert_subject_object:
            object_field = map_field(M.SUBJECT, field_mapping)
        oq_params = params.copy()
        oq_params['fl'] = []
        oq_params['facet.field'] = [object_field]
        oq_params['facet.limit'] = -1
        oq_params['rows'] = 0
        oq_params['facet.mincount'] = 1
        oq_results = solr.search(**oq_params)
        ff = oq_results.facets['facet_fields']
        ofl = ff.get(object_field)
        # solr returns facets counts as list, every 2nd element is number, we don't need the numbers here
        payload['objects'] = ofl[0::2]

    if fetch_subjects:
        core_subject_field = M.SUBJECT
        if slim is not None and len(slim)>0:
            core_subject_field = M.SUBJECT_CLOSURE
        subject_field = map_field(core_subject_field, field_mapping)
        if invert_subject_object:
            subject_field = map_field(M.SUBJECT, field_mapping)
        oq_params = params.copy()
        oq_params['fl'] = []
        oq_params['facet.field'] = [subject_field]
        oq_params['facet.limit'] = MAX_ROWS
        oq_params['rows'] = 0
        oq_params['facet.mincount'] = 1
        oq_results = solr.search(**oq_params)
        ff = oq_results.facets['facet_fields']
        ofl = ff.get(subject_field)
        # solr returns facets counts as list, every 2nd element is number, we don't need the numbers here
        payload['subjects'] = ofl[0::2]
        if len(payload['subjects']) == MAX_ROWS:
            payload['is_truncated'] = True

    if slim is not None and len(slim)>0:
        if 'objects' in payload:
            payload['objects'] = [x for x in payload['objects'] if x in slim]
        if 'associations' in payload:
            for a in payload['associations']:
                a['slim'] = [x for x in a['object_closure'] if x in slim]
                del a['object_closure']

    return payload

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
        for t in slimmed_terms:
            k = (subj,t)
            if k not in pmap:
                pmap[k] = []
            pmap[k].append(a)
    results = [ {'subject': subj, 'slim':t, 'assocs': assocs} for ((subj,t),assocs) in pmap.items()]
    return results
        

def bulk_fetch(subject_category, object_category, taxon, rows=MAX_ROWS, **kwargs):
    """
    Fetch associations for a species and pair of categories in bulk
    """
    time.sleep(1)
    return search_associations_compact(subject_category=subject_category,
                                       object_category=object_category,
                                       subject_taxon=taxon,
                                       rows=rows,
                                       iterative=True,
                                       **kwargs)


def solr_quotify(v):
    if isinstance(v, list):
        return '({})'.format(" OR ".join([solr_quotify(x) for x in v]))
    else:
        # TODO - escape quotes
        return '"{}"'.format(v)

def translate_facet_field(fcs):
    """
    Translates solr facet_fields results into something easier to manipulate

    A solr facet field looks like this: [field1, count1, field2, count2, ..., fieldN, countN]

    We translate this to a dict {f1: c1, ..., fn: cn}

    This has slightly higher overhead for sending over the wire, but is easier to use
    """
    if 'facet_fields' not in fcs:
        return {}
    ffs = fcs['facet_fields']
    rs={}
    for (facet, facetresults) in ffs.items():
        pairs = {}
        rs[facet] = pairs
        for i in range(int(len(facetresults)/2)):
            (fv,fc) = (facetresults[i*2],facetresults[i*2+1])
            pairs[fv] = fc
    return rs

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



# GO-SPECIFIC CODE

def goassoc_fieldmap():
    """
    Returns a mapping of canonical monarch fields to amigo-golr.

    See: https://github.com/geneontology/amigo/blob/master/metadata/ann-config.yaml

    """
    return {
        M.SUBJECT: 'bioentity',
        M.SUBJECT_CLOSURE: 'bioentity',
        M.SUBJECT_LABEL: 'bioentity_label',
        M.SUBJECT_TAXON: 'taxon',
        M.SUBJECT_TAXON_LABEL: 'taxon_label',
        M.SUBJECT_TAXON_CLOSURE: 'taxon_closure',
        M.RELATION: 'qualifier',
        M.OBJECT: 'annotation_class',
        M.OBJECT_CLOSURE: 'isa_partof_closure',
        M.OBJECT_LABEL: 'annotation_class_label',
        M.SUBJECT_CATEGORY: None,
        M.OBJECT_CATEGORY: None,
        M.EVIDENCE_OBJECT_CLOSURE: 'evidence_subset_closure',
        M.IS_DEFINED_BY: 'assigned_by'
    }

def map_field(fn, m) :
    """
    Maps a field name, given a mapping file.
    Returns input if fieldname is unmapped.
    """
    if m is None:
        return fn
    if fn in m:
        return m[fn]
    else:
        return fn

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
