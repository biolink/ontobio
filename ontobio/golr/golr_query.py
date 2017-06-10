"""
A query wrapper for a Golr instance

Intended to work with:

* Monarch golr instance
* AmiGO/GO golr instance (including both GO and Planteome)

Conventions
-----------

Documents follow either entity or association patterns.

Associations
------------

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

import json
import logging
import pysolr

from ontobio.vocabulary.relations import HomologyTypes


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
    OBJECT_TAXON_CLOSURE_LABEL = 'object_taxon_closure_label'
    SUBJECT_GENE_CLOSURE_MAP='subject_gene_closure_map'
    EVIDENCE_OBJECT='evidence_object'
    SUBJECT_TAXON_LABEL_SEARCHABLE='subject_taxon_label_searchable'
    OBJECT_TAXON_LABEL_SEARCHABLE = 'object_taxon_label_searchable'
    IS_DEFINED_BY='is_defined_by'
    SUBJECT_GENE_CLOSURE_LABEL='subject_gene_closure_label'
    EVIDENCE_OBJECT_CLOSURE_LABEL='evidence_object_closure_label'
    SUBJECT_TAXON_CLOSURE='subject_taxon_closure'
    OBJECT_TAXON_CLOSURE = 'object_taxon_closure'
    OBJECT_LABEL='object_label'
    SUBJECT_CATEGORY='subject_category'
    SUBJECT_GENE_LABEL='subject_gene_label'
    SUBJECT_TAXON_CLOSURE_LABEL_SEARCHABLE='subject_taxon_closure_label_searchable'
    OBJECT_TAXON_CLOSURE_LABEL_SEARCHABLE = 'object_taxon_closure_label_searchable'
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
    OBJECT_TAXON = 'object_taxon'
    OBJECT_LABEL_SEARCHABLE='object_label_searchable'
    OBJECT_CATEGORY='object_category'
    SUBJECT_TAXON_CLOSURE_MAP='subject_taxon_closure_map'
    OBJECT_TAXON_CLOSURE_MAP = 'object_taxon_closure_map'
    QUALIFIER='qualifier'
    SUBJECT_TAXON_LABEL='subject_taxon_label'
    OBJECT_TAXON_LABEL = 'object_taxon_label'
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

def flip(d, x, y):
    dx = d.get(x)
    dy = d.get(y)
    d[x] = dy
    d[y] = dx

def solr_quotify(v):
    if isinstance(v, list):
        return '({})'.format(" OR ".join([solr_quotify(x) for x in v]))
    else:
        # TODO - escape quotes
        return '"{}"'.format(v)
    

# We take the monarch golr as default
# Note that these can be overridden using a config object
#monarch_golr_url = "https://solr.monarchinitiative.org/solr/golr/"
#monarch_solr = pysolr.Solr(monarch_golr_url, timeout=5)


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




### GO-SPECIFIC CODE

def goassoc_fieldmap():
    """
    Returns a mapping of canonical monarch fields to amigo-golr.

    See: https://github.com/geneontology/amigo/blob/master/metadata/ann-config.yaml

    """
    return {
        M.SUBJECT: 'bioentity',
        M.SUBJECT_CLOSURE: 'bioentity',
        ## In the GO AmiGO instance, the type field is not correctly populated
        ## See above in the code for hack that restores this for planteome instance
        ## M.SUBJECT_CATEGORY: 'type',
        M.SUBJECT_CATEGORY: None,
        M.SUBJECT_LABEL: 'bioentity_label',
        M.SUBJECT_TAXON: 'taxon',
        M.SUBJECT_TAXON_LABEL: 'taxon_label',
        M.SUBJECT_TAXON_CLOSURE: 'taxon_closure',
        M.RELATION: 'qualifier',
        M.OBJECT: 'annotation_class',
        M.OBJECT_CLOSURE: 'isa_partof_closure',
        M.OBJECT_LABEL: 'annotation_class_label',
        M.OBJECT_TAXON: 'object_taxon',
        M.OBJECT_TAXON_LABEL: 'object_taxon_label',
        M.OBJECT_TAXON_CLOSURE: 'object_taxon_closure',
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


### CLASSES

class GolrServer():
    pass

class GolrAbstractQuery():
    def get_config(self):
        if self.config is None:
            from ontobio.config import Config, get_config
            self.config = get_config()
        return self.config
    
    def _set_solr(self, endpoint):
        self.solr = pysolr.Solr(endpoint.url, timeout=endpoint.timeout)
        return self.solr

    def _use_amigo_schema(self, object_category):
        if object_category is not None and object_category == 'function':
            return True
        ds = self.get_config().default_solr_schema
        if ds is not None and ds == 'amigo':
            return True
        return False

    
class GolrSearchQuery(GolrAbstractQuery):
    """
    Queries over a search document
    """
    def __init__(self,
                 term=None,
                 category=None,
                 is_go=False,
                 url=None,
                 solr=None,
                 config=None,
                 fq=None,
                 hl=True,
                 facet_fields=None,
                 search_fields=None,
                 rows=100):
        self.term = term
        self.category = category
        self.is_go = is_go
        self.url = url
        self.fq = fq
        self.solr = solr
        self.config = config
        self.hl = hl
        self.facet_fields = facet_fields
        self.search_fields = search_fields
        self.rows = rows
        # test if client explicitly passes a URL; do not override
        self.is_explicit_url = url is not None

        if self.facet_fields is None:
            self.facet_fields = ['category','taxon_label']

        if self.search_fields is None:
            self.search_fields = dict(iri=3, id=3, label=2,
                                      definition=2, synonym=2)

    def solr_params(self):
        #facet_fields = [ map_field(fn, self.field_mapping) for fn in self.facet_fields ]

        fq = {}
        if self.category is not None:
            fq['category'] = self.category
        
        qf = []
        suffixes = ['std','kw','eng']
        if self.is_go:
            self.search_fields=dict(entity_label=3,general_blob=3)
            self.hl = False
            # TODO: formal mapping
            if 'taxon_label' in self.facet_fields:
                self.facet_fields.remove('taxon_label')
            suffixes = ['searchable']
            fq['document_category'] = "general"
            if self.url is None:
                self._set_solr(self.get_config().amigo_solr_search)
                #self.url = 'http://golr.berkeleybop.org/'
            else:
                self.solr = pysolr.Solr(self.url, timeout=2)
        else:
            if self.url is None:
                self._set_solr(self.get_config().solr_search)
            else:
                self.solr = pysolr.Solr(self.url, timeout=2)
        
        #if self.url is None:
        #    self.url = 'https://solr-dev.monarchinitiative.org/solr/search'
        #self.solr = pysolr.Solr(self.url, timeout=2)
        
        for (f,relevancy) in self.search_fields.items():
            fmt="{}_{}^{}"
            for suffix in suffixes:
                qf.append(fmt.format(f,suffix,relevancy))
            
        select_fields = ["*","score"]
        params = {
            'q': self.term,
            "qt": "standard",
            'facet': 'on',
            'facet.field': self.facet_fields,
            'facet.limit': 25,
            'fl': ",".join(select_fields),
            "defType": "edismax",
            "qf": qf,
            'rows': self.rows
        }
        if self.hl:
            params['hl.simple.pre'] = "<em class=\"hilite\">"
            params['hl.snippets'] = "1000"
            params['hl'] = 'on'
            
        if fq is not None:
            filter_queries = [ '{}:{}'.format(k,solr_quotify(v)) for (k,v) in fq.items()]
            params['fq'] = filter_queries

        return params

    def exec(self, **kwargs):
        """
        Execute solr query         
        """

        params = self.solr_params()
        logging.info("PARAMS="+str(params))
        results = self.solr.search(**params)
        n_docs = len(results.docs)
        logging.info("Docs found: {}".format(results.hits))
    
        fcs = results.facets

        # map go-golr fields to standard
        for d in results.docs:
            if 'entity' in d:
                d['id'] = d['entity']
                d['label'] = d['entity_label']
        payload = {
            'facet_counts': translate_facet_field(fcs),
            'pagination': {},
            'highlighting': results.highlighting,
            'docs': results.docs
        }
    
        return payload
                 

class GolrAssociationQuery(GolrAbstractQuery):
    """
    A Query object providing a higher level of abstraction over either GO or Monarch Solr indexes

    Fields
    ------

    All of these can be set when creating a new object

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

    evidence: String

        Evidence class from ECO. Inference is used.

    exclude_automatic_assertions : bool

        If true, then any annotations with evidence of ECO:0000501 (IEA) or
        subclasses will be excluded.

    use_compact_associations : bool

        If true, then the associations list will be false, instead
        compact_associations contains a more compact representation
        consisting of objects with (subject, relation and objects)

    config : Config

        See :ref:`Config` for details. The config object can be used
        to set values for the solr instance to be queried
    
    """
    def __init__(self,
                 subject_category=None,
                 object_category=None,
                 relation=None,
                 subject=None,
                 subjects=None,
                 object=None,
                 objects=None,
                 subject_direct=False,
                 subject_taxon=None,
                 object_taxon=None,
                 invert_subject_object=None,
                 evidence=None,
                 exclude_automatic_assertions=False,
                 q=None,
                 id=None,
                 use_compact_associations=False,
                 include_raw=False,
                 field_mapping=None,
                 solr=None,
                 config=None,
                 url=None,
                 select_fields=None,
                 fetch_objects=False,
                 fetch_subjects=False,
                 fq=None,
                 slim=[],
                 json_facet=None,
                 iterate=False,
                 map_identifiers=None,
                 facet_fields=None,
                 facet_field_limits=None,
                 facet_limit=25,
                 facet_mincount=1,
                 facet_pivot_fields=[],
                 facet_on = 'on',
                 pivot_subject_object=False,
                 unselect_evidence=False,
                 rows=10,
                 homology_type=None,
                 **kwargs):

        """Fetch a set of association objects based on a query.


        """
        self.subject_category=subject_category
        self.object_category=object_category
        self.relation=relation
        self.subject=subject
        self.subjects=subjects
        self.object=object
        self.objects=objects
        self.subject_direct=subject_direct
        self.subject_taxon=subject_taxon
        self.object_taxon=object_taxon
        self.invert_subject_object=invert_subject_object
        self.evidence=evidence
        self.exclude_automatic_assertions=exclude_automatic_assertions
        self.id=id
        self.q=q
        self.use_compact_associations=use_compact_associations
        self.include_raw=include_raw
        self.field_mapping=field_mapping
        self.solr=solr
        self.config = config
        self.select_fields=select_fields
        self.fetch_objects=fetch_objects
        self.fetch_subjects=fetch_subjects
        self.fq=fq
        self.slim=slim
        self.json_facet=json_facet
        self.iterate=iterate
        self.map_identifiers=map_identifiers
        self.facet_fields=facet_fields
        self.facet_field_limits=facet_field_limits
        self.facet_limit=facet_limit
        self.facet_mincount=facet_mincount
        self.facet_pivot_fields=facet_pivot_fields
        self.facet_on=facet_on
        self.pivot_subject_object=pivot_subject_object
        self.unselect_evidence=unselect_evidence
        self.max_rows=100000
        self.rows=rows
        self.homology_type = homology_type
        self.url = url
        # test if client explicitly passes a URL; do not override
        self.is_explicit_url = url is not None

        if self.facet_fields is None:
            self.facet_fields = [
                M.SUBJECT_TAXON_LABEL,
                M.OBJECT_CLOSURE
            ]

    def adjust(self):
        pass

    def solr_params(self):
        """
        Generate HTTP parameters for passing to Solr.

        In general you should not need to call this directly, calling exec() on a query object
        will transparently perform this step for you.
        """

        ## Main query params for solr
        fq=self.fq
        if fq is None:
            fq = {}
        logging.info("TEMPx FQ={}".format(fq))
        
        
        # canonical form for MGI is a CURIE MGI:nnnn
        #if subject is not None and subject.startswith('MGI:MGI:'):
        #    logging.info('Unhacking MGI ID presumably from GO:'+str(subject))
        #    subject = subject.replace("MGI:MGI:","MGI")
        subject=self.subject
        if subject is not None:
            subject = self.make_canonical_identifier(subject)
        subjects=self.subjects
        if subjects is not None:
            subjects = [self.make_canonical_identifier(s) for s in subjects]
    
        # temporary: for querying go solr, map fields. TODO
        object_category=self.object_category
        logging.info("Object category: {}".format(object_category))
        
        object=self.object
        if object_category is None and object is not None and object.startswith('GO:'):
            # Infer category
            object_category = 'function'
            logging.info("Inferring Object category: {} from {}".
                         format(object_category, object))

        if self.solr is None:
            if self.url is None:
                self._set_solr(self.get_config().solr_assocs)
                #self.solr = monarch_solr
            else:
                self.solr = pysolr.Solr(self.url, timeout=5)
                
        # URL to use for querying solr
        if self._use_amigo_schema(object_category):
            if self.url is None:
                self._set_solr(self.get_config().amigo_solr_assocs)
                #go_golr_url = "http://golr.berkeleybop.org/solr/"
                #self.solr = pysolr.Solr(go_golr_url, timeout=5)
            self.field_mapping=goassoc_fieldmap()

            # awkward hack: we want to avoid typing on the amigo golr gene field,
            # UNLESS this is a planteome golr
            if "planteome" in self.get_config().amigo_solr_assocs.url:
                self.field_mapping[M.SUBJECT_CATEGORY] = 'type'
                
            fq['document_category'] = 'annotation'
            if subject is not None:
                subject = self.make_gostyle_identifier(subject)
            if subjects is not None:
                subjects = [self.make_gostyle_identifier(s) for s in subjects]

            # the AmiGO schema lacks an object_category field;
            # we could use the 'aspect' field but instead we use a mapping of
            # the category to a root class
            if object_category is not None:
                cc = self.get_config().get_category_class(object_category)
                if cc is not None and object == None:
                    object = cc
    
        ## subject params
        subject_taxon=self.subject_taxon
        subject_category=self.subject_category

        # heuristic procedure to guess unspecified subject_category
        if subject_category is None and subject is not None:
            subject_category = self.infer_category(subject)
        
        if subject_category is not None and subject_category == 'disease':
            if subject_taxon is not None and subject_taxon=='NCBITaxon:9606':
                logging.info("Unsetting taxon, until indexed correctly")
                subject_taxon = None
    
        if self.invert_subject_object is None:
            # TODO: consider placing in a separate lookup
            p = (subject_category,object_category)
            if p == ('disease','gene'):
                self.invert_subject_object = True
            elif p == ('disease','model'):
                self.invert_subject_object = True
            else:
                self.invert_subject_object = False
            if self.invert_subject_object:
                logging.info("Inferred that subject/object should be inverted for {}".format(p))
                
        ## taxon of object of triple
        object_taxon=self.object_taxon
        
        # typically information is stored one-way, e.g. model-disease;
        # sometimes we want associations from perspective of object
        if self.invert_subject_object:
            (subject,object) = (object,subject)
            (subject_category,object_category) = (object_category,subject_category)
            (subject_taxon,object_taxon) = (object_taxon,subject_taxon)

        ## facet fields
        facet_fields=self.facet_fields
        facet_on=self.facet_on
        facet_limit=self.facet_limit
        select_fields=self.select_fields
            
        if self.use_compact_associations:
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
            if self.subject_direct:
                fq['subject'] = subject
            else:
                fq['subject_closure'] = subject
        if subjects is not None:
            # lists are assumed to be disjunctive
            if self.subject_direct:
                fq['subject'] = subjects
            else:
                fq['subject_closure'] = subjects
                
        objects=self.objects
        if objects is not None:
            # lists are assumed to be disjunctive
            fq['object_closure'] = objects
        relation=self.relation
        if relation is not None:
            fq['relation_closure'] = relation
        if subject_taxon is not None:
            fq['subject_taxon_closure'] = subject_taxon
        if object_taxon is not None:
            fq['object_taxon_closure'] = object_taxon
        if self.id is not None:
            fq['id'] = self.id
        if self.evidence is not None:
            e = self.evidence
            if e.startswith("-"):
                fq['-evidence_object_closure'] = e.replace("-","")
            else:
                fq['evidence_object_closure'] = e
                
        if self.exclude_automatic_assertions:
            fq['-evidence_object_closure'] = 'ECO:0000501'

        # Homolog service params
        # TODO can we sync with argparse.choices?
        if self.homology_type is not None:
            if self.homology_type == 'O':
                fq['relation_closure'] = HomologyTypes.Ortholog.value
            elif self.homology_type == 'P':
                fq['relation_closure'] = HomologyTypes.Paralog.value
            elif self.homology_type == 'LDO':
                fq['relation_closure'] = \
            HomologyTypes.LeastDivergedOrtholog.value

            
        ## pivots
        facet_pivot_fields=self.facet_pivot_fields
        if self.pivot_subject_object:
            facet_pivot_fields = [M.SUBJECT, M.OBJECT]
    
    
        # Map solr field names for fq. The generic Monarch schema is
        # canonical, GO schema is mapped to this using
        # field_mapping dictionary
        if self.field_mapping is not None:
            for (k,v) in self.field_mapping.items():
    
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
        if self.q is not None:
            qstr = self.q
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
                M.OBJECT_TAXON,
                M.OBJECT_TAXON_LABEL
            ]
            if not self.unselect_evidence:
                select_fields += [
                    M.EVIDENCE_OBJECT,
                    M.EVIDENCE_GRAPH
                ]
    
        if self.map_identifiers is not None:
            select_fields.append(M.SUBJECT_CLOSURE)
    
        if self.slim is not None and len(self.slim)>0:
            select_fields.append(M.OBJECT_CLOSURE)
    
        if self.field_mapping is not None:
            logging.info("Applying field mapping to SELECT: {}".format(self.field_mapping))
            select_fields = [ map_field(fn, self.field_mapping) for fn in select_fields ]
            if facet_pivot_fields is not None:
                logging.info("Applying field mapping to PIV: {}".format(facet_pivot_fields))
                facet_pivot_fields = [ map_field(fn, self.field_mapping) for fn in facet_pivot_fields ]
                logging.info("APPLIED field mapping to PIV: {}".format(facet_pivot_fields))
                
        facet_fields = [ map_field(fn, self.field_mapping) for fn in facet_fields ]
    
        ## true if iterate in windows of max_size until all results found
        iterate=self.iterate
        
        #logging.info('FL'+str(select_fields))
        is_unlimited = False
        rows=self.rows
        if rows < 0:
            is_unlimited = True
            iterate = True
            rows = self.max_rows
        params = {
            'q': qstr,
            'fq': filter_queries,
            'facet': facet_on,
            'facet.field': facet_fields,
            'facet.limit': facet_limit,
            'facet.mincount': self.facet_mincount,
            'fl': ",".join(select_fields),
            'rows': rows
        }
        json_facet=self.json_facet
        if json_facet:
            params['json.facet'] = json.dumps(json_facet)
    
        facet_field_limits=self.facet_field_limits
        if facet_field_limits is not None:
            for (f,flim) in facet_field_limits.items():
                params["f."+f+".facet.limit"] = flim
    
    
        if len(facet_pivot_fields) > 0:
            params['facet.pivot'] = ",".join(facet_pivot_fields)
            params['facet.pivot.mincount'] = 1
            
        return params
            
    def exec(self, **kwargs):
        """
        Execute solr query

        Result object is a dict with the following keys:

         - raw
         - associations : list
         - compact_associations : list
         - facet_counts
         - facet_pivot
         
        """

        params = self.solr_params()
        logging.info("PARAMS="+str(params))
        results = self.solr.search(**params)
        n_docs = len(results.docs)
        logging.info("Docs found: {}".format(results.hits))
    
        if self.iterate:
            docs = results.docs
            start = n_docs
            while n_docs >= self.rows:
                logging.info("Iterating; start={}".format(start))
                next_results = self.solr.search(**params, start=start)
                next_docs = next_results.docs
                n_docs = len(next_docs)
                docs += next_docs
                start += self.rows
            results.docs = docs

        fcs = results.facets
    
        payload = {
            'facet_counts': translate_facet_field(fcs),
            'pagination': {}
        }
    
        include_raw=self.include_raw
        if include_raw:
            # note: this is not JSON serializable, do not send via REST
            payload['raw'] = results
    
        # TODO - check if truncated
    
        logging.info("COMPACT={} INV={}".format(self.use_compact_associations, self.invert_subject_object))
        if self.use_compact_associations:
            payload['compact_associations'] = self.translate_docs_compact(results.docs, field_mapping=self.field_mapping,
                                                                     slim=self.slim, invert_subject_object=self.invert_subject_object,
                                                                     map_identifiers=self.map_identifiers, **kwargs)
        else:
            payload['associations'] = self.translate_docs(results.docs, field_mapping=self.field_mapping, map_identifiers=self.map_identifiers, **kwargs)
    
        if 'facet_pivot' in fcs:
            payload['facet_pivot'] = fcs['facet_pivot']
        if 'facets' in results.raw_response:
            payload['facets'] = results.raw_response['facets']
    
        # For solr, we implement this by finding all facets
        # TODO: no need to do 2nd query, see https://wiki.apache.org/solr/SimpleFacetParameters#Parameters
        fetch_objects=self.fetch_objects
        if fetch_objects:
            core_object_field = M.OBJECT
            if self.slim is not None and len(self.slim)>0:
                core_object_field = M.OBJECT_CLOSURE
            object_field = map_field(core_object_field, self.field_mapping)
            if self.invert_subject_object:
                object_field = map_field(M.SUBJECT, self.field_mapping)
            oq_params = params.copy()
            oq_params['fl'] = []
            oq_params['facet.field'] = [object_field]
            oq_params['facet.limit'] = -1
            oq_params['rows'] = 0
            oq_params['facet.mincount'] = 1
            oq_results = self.solr.search(**oq_params)
            ff = oq_results.facets['facet_fields']
            ofl = ff.get(object_field)
            # solr returns facets counts as list, every 2nd element is number, we don't need the numbers here
            payload['objects'] = ofl[0::2]
    
        fetch_subjects=self.fetch_subjects
        if fetch_subjects:
            core_subject_field = M.SUBJECT
            if self.slim is not None and len(self.slim)>0:
                core_subject_field = M.SUBJECT_CLOSURE
            subject_field = map_field(core_subject_field, self.field_mapping)
            if self.invert_subject_object:
                subject_field = map_field(M.SUBJECT, self.field_mapping)
            oq_params = params.copy()
            oq_params['fl'] = []
            oq_params['facet.field'] = [subject_field]
            oq_params['facet.limit'] = self.max_rows
            oq_params['rows'] = 0
            oq_params['facet.mincount'] = 1
            oq_results = self.solr.search(**oq_params)
            ff = oq_results.facets['facet_fields']
            ofl = ff.get(subject_field)
            # solr returns facets counts as list, every 2nd element is number, we don't need the numbers here
            payload['subjects'] = ofl[0::2]
            if len(payload['subjects']) == self.max_rows:
                payload['is_truncated'] = True
    
        if self.slim is not None and len(self.slim)>0:
            if 'objects' in payload:
                payload['objects'] = [x for x in payload['objects'] if x in self.slim]
            if 'associations' in payload:
                for a in payload['associations']:
                    a['slim'] = [x for x in a['object_closure'] if x in self.slim]
                    del a['object_closure']
    
        return payload
            
    def infer_category(self, id):
        """
        heuristic to infer a category from an id, e.g. DOID:nnn --> disease
        """
        logging.info("Attempting category inference on id={}".format(id))
        toks = id.split(":")
        idspace = toks[0]
        c = None
        if idspace == 'DOID':
            c='disease'
        if c is not None:
            logging.info("Inferred category: {} based on id={}".format(c, id))
        return c
        

    def make_canonical_identifier(self,id):
        """
        E.g. MGI:MGI:nnnn --> MGI:nnnn
        """
        if id is not None:
            for (k,v) in PREFIX_NORMALIZATION_MAP.items():
                s = k+':'
                if id.startswith(s):
                    return id.replace(s,v+':')
        return id

    def make_gostyle_identifier(self,id):
        """
        E.g. MGI:nnnn --> MGI:MGI:nnnn
        """
        if id is not None:
            for (k,v) in PREFIX_NORMALIZATION_MAP.items():
                s = v+':'
                if id.startswith(s):
                    return id.replace(s,k+':')
        return id
        
    
    def translate_objs(self,d,fname):
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
    
    
    def translate_obj(self,d,fname):
        """
        Translate a field value from a solr document.
    
        This includes special logic for when the field value
        denotes an object, here we nest it
        """
        if fname not in d:
            # TODO: consider adding arg for failure on null
            return None
    
        lf = M.label_field(fname)
    
        gq = GolrAssociationQuery() ## TODO - make this a class method
        id = d[fname]                
        id = self.make_canonical_identifier(id)
        #if id.startswith('MGI:MGI:'):
        #    id = id.replace('MGI:MGI:','MGI:')
        obj = {'id': id}
    
        if lf in d:
            obj['label'] = d[lf]
    
        cf = fname + "_category"
        if cf in d:
            obj['categories'] = [d[cf]]
    
        return obj
    
    def map_doc(self, d, field_mapping, invert_subject_object=False):
        if field_mapping is not None:
            for (k,v) in field_mapping.items():
                if v is not None and k is not None:
                    #logging.debug("TESTING FOR:"+v+" IN "+str(d))
                    if v in d:
                        #logging.debug("Setting field {} to {} // was in {}".format(k,d[v],v))
                        d[k] = d[v]
        if invert_subject_object:
            flip(d,M.SUBJECT,M.OBJECT)
            flip(d,M.SUBJECT_LABEL,M.OBJECT_LABEL)
            flip(d,M.SUBJECT_CATEGORY,M.OBJECT_CATEGORY)
        return d
    
    
    def translate_doc(self, d, field_mapping=None, map_identifiers=None, **kwargs):
        """
        Translate a solr document (i.e. a single result row)
        """
        if field_mapping is not None:
            self.map_doc(d, field_mapping)
        subject = self.translate_obj(d, M.SUBJECT)
        obj = self.translate_obj(d, M.OBJECT)
    
        # TODO: use a more robust method; we need equivalence as separate field in solr
        if map_identifiers is not None:
            if M.SUBJECT_CLOSURE in d:
                subject['id'] = self.map_id(subject, map_identifiers, d[M.SUBJECT_CLOSURE])
            else:
                logging.info("NO SUBJECT CLOSURE IN: "+str(d))
    
        if M.SUBJECT_TAXON in d:
            subject['taxon'] = self.translate_obj(d,M.SUBJECT_TAXON)
        if M.OBJECT_TAXON in d:
            obj['taxon'] = self.translate_obj(d, M.OBJECT_TAXON)

        qualifiers = []
        if M.RELATION in d and isinstance(d[M.RELATION],list):
            # GO overloads qualifiers and relation
            relation = None
            for rel in d[M.RELATION]:
                if rel.lower() == 'not':
                    qualifiers.append(rel)
                else:
                    relation = rel
            if relation is not None:
                d[M.RELATION] = relation
            else:
                d[M.RELATION] = None

        negated = 'not' in qualifiers        
        
        assoc = {'id':d.get(M.ID),
                 'subject': subject,
                 'object': obj,
                 'negated': negated,
                 'relation': self.translate_obj(d,M.RELATION),
                 'publications': self.translate_objs(d,M.SOURCE),  # note 'source' is used in the golr schema
        }
        if len(qualifiers) > 0:
            assoc['qualifiers'] = qualifiers
            
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
    
    def translate_docs(self, ds, **kwargs):
        """
        Translate a set of solr results
        """
        return [self.translate_doc(d, **kwargs) for d in ds]
    
    
    def translate_docs_compact(self, ds, field_mapping=None, slim=None, map_identifiers=None, invert_subject_object=False, **kwargs):
        """
        Translate golr association documents to a compact representation
        """
        amap = {}
        logging.info("Translating docs to compact form. Slim={}".format(slim))
        for d in ds:
            self.map_doc(d, field_mapping, invert_subject_object=invert_subject_object)
    
            subject = d[M.SUBJECT]
            subject_label = d[M.SUBJECT_LABEL]
    
            # TODO: use a more robust method; we need equivalence as separate field in solr
            if map_identifiers is not None:
                if M.SUBJECT_CLOSURE in d:
                    subject = self.map_id(subject, map_identifiers, d[M.SUBJECT_CLOSURE])
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
    
            subject = self.make_canonical_identifier(subject)
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
    
    def map_id(self,id, prefix, closure_list):
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
    

    
