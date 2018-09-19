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
import requests
from typing import Dict, List
import xml.etree.ElementTree as ET
from collections import OrderedDict
from ontobio.vocabulary.relations import HomologyTypes
from ontobio.model.GolrResults import SearchResults, AutocompleteResult, Highlight
from ontobio.util.user_agent import get_user_agent


INVOLVED_IN="involved_in"
ACTS_UPSTREAM_OF_OR_WITHIN="acts_upstream_of_or_within"

ISA_PARTOF_CLOSURE="isa_partof_closure"
REGULATES_CLOSURE="regulates_closure"

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

    # This is a temporary fix until
    # https://github.com/biolink/ontobio/issues/126 is resolved.

    # AmiGO specific fields
    AMIGO_SPECIFIC_FIELDS = [
        'reference',
        'qualifier',
        'is_redundant_for',
        'type',
        'evidence',
        'evidence_label',
        'evidence_type',
        'evidence_type_label',
        'evidence_with',
        'evidence_closure',
        'evidence_closure_label',
        'evidence_subset_closure',
        'evidence_subset_closure_label',
        'evidence_type_closure',
        'evidence_type_closure_label'
    ]

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

# fields in the result docs that are to be inverted when 'invert_subject_object' is True
INVERT_FIELDS_MAP = {
    M.SUBJECT: M.OBJECT,
    M.SUBJECT_CLOSURE: M.OBJECT_CLOSURE,
    M.SUBJECT_TAXON: M.OBJECT_TAXON,
    M.SUBJECT_CLOSURE_LABEL: M.OBJECT_CLOSURE_LABEL,
    M.SUBJECT_TAXON_CLOSURE_LABEL: M.OBJECT_TAXON_CLOSURE_LABEL,
    M.SUBJECT_TAXON_LABEL_SEARCHABLE: M.OBJECT_TAXON_LABEL_SEARCHABLE,
    M.SUBJECT_TAXON_CLOSURE: M.OBJECT_TAXON_CLOSURE,
    M.SUBJECT_LABEL: M.OBJECT_LABEL,
    M.SUBJECT_TAXON_CLOSURE_LABEL_SEARCHABLE: M.OBJECT_TAXON_CLOSURE_LABEL_SEARCHABLE,
    M.SUBJECT_CLOSURE_LABEL_SEARCHABLE: M.OBJECT_CLOSURE_LABEL_SEARCHABLE,
    M.SUBJECT_LABEL_SEARCHABLE: M.OBJECT_LABEL_SEARCHABLE,
    M.SUBJECT_CATEGORY: M.OBJECT_CATEGORY,
    M.SUBJECT_TAXON_CLOSURE_MAP: M.OBJECT_TAXON_CLOSURE_MAP,
    M.SUBJECT_TAXON_LABEL: M.OBJECT_TAXON_LABEL,
    M.SUBJECT_CLOSURE_MAP: M.OBJECT_CLOSURE_MAP,
}

# normalize to what Monarch uses
PREFIX_NORMALIZATION_MAP = {
    'MGI:MGI' : 'MGI',
    'FB' : 'FlyBase',
}

def flip(d, x, y):
    dx = d.get(x)
    dy = d.get(y)
    d[x] = dy
    d[y] = dx

def solr_quotify(v):
    if isinstance(v, list):
        if len(v) == 1:
            return solr_quotify(v[0])
        else:
            return '({})'.format(" OR ".join([solr_quotify(x) for x in v]))
    else:
        # TODO - escape quotes
        return '"{}"'.format(v)


# We take the monarch golr as default
# Note that these can be overridden using a config object
#monarch_golr_url = "https://solr.monarchinitiative.org/solr/golr/"
#monarch_solr = pysolr.Solr(monarch_golr_url, timeout=5)


def translate_facet_field(fcs, invert_subject_object = False):
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
        if invert_subject_object:
            for (k,v) in INVERT_FIELDS_MAP.items():
                if facet == k:
                    facet = v
                    break
                elif facet == v:
                    facet = k
                    break

        pairs = {}
        rs[facet] = pairs
        for i in range(int(len(facetresults)/2)):
            (fv,fc) = (facetresults[i*2],facetresults[i*2+1])
            pairs[fv] = fc
    return rs




### GO-SPECIFIC CODE

def goassoc_fieldmap(relationship_type=ACTS_UPSTREAM_OF_OR_WITHIN):
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
        M.OBJECT_CLOSURE: REGULATES_CLOSURE if relationship_type == ACTS_UPSTREAM_OF_OR_WITHIN else ISA_PARTOF_CLOSURE,
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

    def _set_solr(self, url, timeout=2):
        self.solr = pysolr.Solr(url=url, timeout=timeout)
        return self.solr

    def _set_user_agent(self, user_agent):
        self.solr.get_session().headers['User-Agent'] = user_agent

    def _use_amigo_schema(self, object_category):
        if object_category is not None and object_category == 'function':
            return True
        ds = self.get_config().default_solr_schema
        if ds is not None and ds == 'amigo':
            return True
        return False


class GolrSearchQuery(GolrAbstractQuery):
    """
    Controller for monarch and go solr search cores
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
                 facet=True,
                 search_fields=None,
                 rows=100,
                 start=None,
                 prefix=None,
                 boost_fx=None,
                 boost_q=None,
                 highlight_class=None,
                 taxon=None,
                 user_agent=None):
        self.term = term
        self.category = category
        self.is_go = is_go
        self.url = url
        self.solr = solr
        self.config = config
        self.hl = hl
        self.facet = facet
        self.facet_fields = facet_fields
        self.search_fields = search_fields
        self.rows = rows
        self.start = start
        # test if client explicitly passes a URL; do not override
        self.is_explicit_url = url is not None
        self.fq = fq if fq is not None else {}
        self.prefix = prefix
        self.boost_fx = boost_fx
        self.boost_q = boost_q
        self.highlight_class = highlight_class
        self.taxon = taxon

        self.user_agent = get_user_agent(modules=[requests, pysolr], caller_name=__name__)
        if user_agent is not None:
             self.user_agent += " {}".format(user_agent)

        if self.search_fields is None:
            self.search_fields = dict(id=3,
                                      iri=3,
                                      label=2,
                                      synonym=1,
                                      definition=1,
                                      taxon_label=1,
                                      equivalent_iri=1,
                                      equivalent_curie=1)

        solr_config = {'url': self.url, 'timeout': 2}
        if self.is_go:
            if self.url is None:
                endpoint = self.get_config().amigo_solr_search
                solr_config = {'url': endpoint.url, 'timeout': endpoint.timeout}

            else:
                solr_config = {'url': self.url, 'timeout': 2}
        else:
            if self.url is None:
                endpoint = self.get_config().solr_search
                solr_config = {'url': endpoint.url, 'timeout': endpoint.timeout}
            else:
                solr_config = {'url': self.url, 'timeout': 2}

        self._set_solr(**solr_config)
        self._set_user_agent(self.user_agent)

    def update_solr_url(self, url, timeout=2):
        self.url = url
        solr_config = {'url': url, 'timeout': timeout}
        self._set_solr(**solr_config)
        self._set_user_agent(self.user_agent)

    def solr_params(self):

        if self.facet_fields is None and self.facet:
            self.facet_fields = ['category', 'taxon_label']

        if self.category is not None:
            self.fq['category'] = self.category

        suffixes = ['std', 'kw', 'eng']
        if self.is_go:
            self.search_fields=dict(entity_label=3, general_blob=3)
            self.hl = False
            # TODO: formal mapping
            if 'taxon_label' in self.facet_fields:
                self.facet_fields.remove('taxon_label')
            suffixes = ['searchable']
            self.fq['document_category'] = "general"

        qf = self._format_query_filter(self.search_fields, suffixes)

        if self.term is not None and ":" in self.term:
            qf["id_kw"] = 20
            qf["equivalent_curie_kw"] = 20

        select_fields = ["*", "score"]
        params = {
            'q': '{0} "{0}"'.format(self.term),
            "qt": "standard",
            'fl': ",".join(select_fields),
            "defType": "edismax",
            "qf": ["{}^{}".format(field, weight) for field, weight in qf.items()],
            'rows': self.rows
        }

        if self.facet:
            params['facet'] = 'on'
            params['facet.field'] = self.facet_fields
            params['facet.limit'] = 25
            params['facet.mincount'] = 1

        if self.start is not None:
            params['start'] = self.start

        if self.hl:
            params['hl.simple.pre'] = "<em class=\"hilite\">"
            params['hl.snippets'] = "1000"
            params['hl'] = 'on'

        if self.fq is not None:
            filter_queries = ['{}:{}'.format(k,solr_quotify(v))
                              for (k,v) in self.fq.items()]
            params['fq'] = filter_queries
        else:
            params['fq'] = []

        if self.prefix is not None:
            negative_filter = [p_filt for p_filt in self.prefix
                               if p_filt.startswith('-')]
            positive_filter = [p_filt for p_filt in self.prefix
                               if not p_filt.startswith('-')]
            for pfix_filter in negative_filter:
                params['fq'].append('-prefix:"{}"'.format(pfix_filter[1:]))

            if len(positive_filter) > 0:
                or_filter = 'prefix:"{}"'.format(positive_filter[0])
                for pfix_filter in positive_filter[1:]:
                    or_filter += ' OR prefix:"{}"'.format(pfix_filter)
                params['fq'].append(or_filter)

        if self.boost_fx is not None:
            params['bf'] = []
            for boost in self.boost_fx:
                params['bf'].append(boost)

        if self.boost_q is not None:
            params['bq'] = []
            for boost in self.boost_q:
                params['bq'].append(boost)

        if self.taxon is not None:
            for tax in self.taxon:
                params['fq'].append('taxon:"{}"'.format(tax))

        if self.highlight_class is not None:
            params['hl.simple.pre'] = \
                '<em class=\"{}\">'.format(self.highlight_class)

        return params

    def search(self):
        """
        Execute solr search query
        """
        params = self.solr_params()
        logging.info("PARAMS=" + str(params))
        results = self.solr.search(**params)
        logging.info("Docs found: {}".format(results.hits))
        return self._process_search_results(results)

    def autocomplete(self):
        """
        Execute solr autocomplete
        """
        self.facet = False
        params = self.solr_params()
        logging.info("PARAMS=" + str(params))
        results = self.solr.search(**params)
        logging.info("Docs found: {}".format(results.hits))
        return self._process_autocomplete_results(results)

    def _process_search_results(self,
                                results: pysolr.Results) -> SearchResults:
        """
        Convert solr docs to biolink object

        :param results: pysolr.Results
        :return: model.GolrResults.SearchResults
        """

        # map go-golr fields to standard
        for doc in results.docs:
            if 'entity' in doc:
                doc['id'] = doc['entity']
                doc['label'] = doc['entity_label']

        highlighting = {
            doc['id']: self._process_highlight(results, doc)._asdict()
            for doc in results.docs if results.highlighting
        }
        payload = SearchResults(
            facet_counts=translate_facet_field(results.facets),
            highlighting=highlighting,
            docs=results.docs,
            numFound=results.hits
        )
        logging.debug('Docs: {}'.format(len(results.docs)))

        return payload

    def _process_autocomplete_results(
            self,
            results: pysolr.Results) -> Dict[str, List[AutocompleteResult]]:
        """
        Convert results to biolink autocomplete object
        :param results: pysolr.Results
        :return: {'docs': List[AutocompleteResult]}
        """
        # map go-golr fields to standard
        for doc in results.docs:
            if 'entity' in doc:
                doc['id'] = doc['entity']
                doc['label'] = doc['entity_label']

        docs = []
        for doc in results.docs:
            if results.highlighting:
                hl = self._process_highlight(results, doc)
            else:
                hl = Highlight(None, None, None)

            # In some cases a node does not have a category
            category = doc['category'] if 'category' in doc else []

            doc['taxon'] = doc['taxon'] if 'taxon' in doc else ""
            doc['taxon_label'] = doc['taxon_label'] if 'taxon_label' in doc else ""
            doc = AutocompleteResult(
                id=doc['id'],
                label=doc['label'],
                match=hl.match,
                category=category,
                taxon=doc['taxon'],
                taxon_label=doc['taxon_label'],
                highlight=hl.highlight,
                has_highlight=hl.has_highlight
            )
            docs.append(doc)

        payload = {
            'docs': docs
        }
        logging.debug('Docs: {}'.format(len(results.docs)))

        return payload

    def _process_highlight(self, results: pysolr.Results, doc) -> Highlight:
        hl = results.highlighting[doc['id']]
        highlights = []
        for hl_list in hl.values():
            highlights.extend(hl_list)
        try:
            highlight = Highlight(
                highlight=self._get_longest_hl(highlights),
                match=self._hl_as_string(self._get_longest_hl(highlights)),
                has_highlight=True
            )
        except ET.ParseError:
            highlight = Highlight(
                highlight=doc['label'][0],
                match=doc['label'][0],
                has_highlight=False
            )
        return highlight

    @staticmethod
    def _format_query_filter(search_fields, suffixes):
        qf = {}
        for (field, relevancy) in search_fields.items():
            for suffix in suffixes:
                field_filter = "{}_{}".format(field, suffix)
                weight = "{}".format(relevancy)
                qf[field_filter] = weight
        return qf

    def _get_longest_hl(self, highlights):
        """
        Given a list of highlighted text, returns the
        longest highlight
        For example:
        [
            "<em>Muscle</em> <em>atrophy</em>, generalized",
            "Generalized <em>muscle</em> degeneration",
            "Diffuse skeletal <em>">muscle</em> wasting"
        ]
        and returns:
            <em>Muscle</em> <em>atrophy</em>, generalized

        If there are mutliple matches of the same length, returns
        the top (arbitrary) highlight
        :return:
        """
        len_dict = OrderedDict()
        for hl in highlights:
            # dummy tags to make it valid xml
            dummy_xml = "<p>" + hl + "</p>"
            try:
                element_tree = ET.fromstring(dummy_xml)
                hl_length = 0
                for emph in element_tree.findall('em'):
                    hl_length += len(emph.text)
                len_dict[hl] = hl_length
            except ET.ParseError:
                raise ET.ParseError

        return max(len_dict, key=len_dict.get)

    def _hl_as_string(self, highlight):
        """
        Given a solr string of highlighted text, returns the
        str representations
        For example:
        "Foo <em>Muscle</em> bar <em>atrophy</em>, generalized"
        Returns:
        "Foo Muscle bar atrophy, generalized"
        :return: str
        """
        # dummy tags to make it valid xml
        dummy_xml = "<p>" + highlight + "</p>"
        try:
            element_tree = ET.fromstring(dummy_xml)
        except ET.ParseError:
            raise ET.ParseError
        return "".join(list(element_tree.itertext()))


class GolrLayPersonSearch(GolrSearchQuery):
    """
    Controller for the HPO lay person index,
    see https://github.com/monarch-initiative/hpo-plain-index
    """

    def __init__(self, term=None, **kwargs):
        super().__init__(term, **kwargs)
        self.facet = False
        endpoint = self.get_config().lay_person_search
        self._set_solr(endpoint.url, endpoint.timeout)
        self._set_user_agent(self.user_agent)

    def set_lay_params(self):
        params = self.solr_params()
        suffixes = ['std', 'kw', 'eng']
        qf = self._get_default_weights(suffixes)
        params['qf'] = ["{}^{}".format(field, weight) for field, weight in qf.items()]
        return params

    def autocomplete(self):
        """
        Execute solr query for autocomplete
        """
        params = self.set_lay_params()
        logging.info("PARAMS="+str(params))
        results = self.solr.search(**params)
        logging.info("Docs found: {}".format(results.hits))
        return self._process_layperson_results(results)

    def _process_layperson_results(self, results):
        """
        Convert pysolr.Results to biolink object
        :param results:
        :return:
        """

        payload = {
            'results': []
        }

        for doc in results.docs:
            hl = self._process_highlight(results, doc)
            highlight = {
                'id': doc['id'],
                'highlight': hl.highlight,
                'label': doc['label'],
                'matched_synonym': hl.match
            }
            payload['results'].append(highlight)

        logging.debug('Docs: {}'.format(len(results.docs)))

        return payload

    @staticmethod
    def _get_default_weights(suffixes):
        """
        Defaults for the plain language index
        :param suffixes: list of suffixes (eng (ngram), std,)
        :return:
        """
        weights = {
            "exact_synonym":   "5",
            "related_synonym": "2",
            "broad_synonym":   "1",
            "narrow_synonym":  "3"
        }
        qf = GolrLayPersonSearch._format_query_filter(weights, suffixes)
        return qf


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
                 relationship_type=None,
                 subject_or_object_ids=None,
                 subject_or_object_category=None,
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
                 slim=None,
                 json_facet=None,
                 iterate=False,
                 map_identifiers=None,
                 facet_fields=None,
                 facet_field_limits=None,
                 facet_limit=25,
                 facet_mincount=1,
                 facet_pivot_fields=None,
                 facet_on = 'on',
                 pivot_subject_object=False,
                 unselect_evidence=False,
                 rows=10,
                 start=None,
                 homology_type=None,
                 non_null_fields=None,
                 user_agent=None,
                 **kwargs):

        """Fetch a set of association objects based on a query.


        """
        self.subject_category=subject_category
        self.object_category=object_category
        self.relation=relation
        self.relationship_type=relationship_type
        self.subject_or_object_ids=subject_or_object_ids
        self.subject_or_object_category=subject_or_object_category
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
        self.fq=fq if fq is not None else {}
        self.slim = slim if slim is not None else []
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
        self.start=start
        self.homology_type = homology_type
        self.url = url
        # test if client explicitly passes a URL; do not override
        self.is_explicit_url = url is not None
        self.non_null_fields=non_null_fields

        self.user_agent = get_user_agent(modules=[requests, pysolr], caller_name=__name__)
        if user_agent is not None:
             self.user_agent += " {}".format(user_agent)

        if self.facet_pivot_fields is None:
            self.facet_pivot_fields = []

        if self.non_null_fields is None:
            self.non_null_fields = []

        if self.facet_fields is None:
            self.facet_fields = [
                M.SUBJECT_TAXON_LABEL,
                M.OBJECT_CLOSURE
            ]

    def update_solr_url(self, url, timeout=2):
        self.url = url
        solr_config = {'url': url, 'timeout': timeout}
        self._set_solr(**solr_config)
        self._set_user_agent(self.user_agent)

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

        # subject_or_object_ids is a list of identifiers that can be matched to either subjects or objects
        subject_or_object_ids = self.subject_or_object_ids
        if subject_or_object_ids is not None:
            subject_or_object_ids = [self.make_canonical_identifier(c) for c in subject_or_object_ids]

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

        solr_config = {'url': self.url, 'timeout': 5}
        if self.solr is None:
            if self.url is None:
                endpoint = self.get_config().solr_assocs
                solr_config = {'url': endpoint.url, 'timeout': endpoint.timeout}
            else:
                solr_config = {'url': self.url, 'timeout': 5}

        # URL to use for querying solr
        if self._use_amigo_schema(object_category):
            if self.url is None:
                endpoint = self.get_config().amigo_solr_assocs
                solr_config = {'url': endpoint.url, 'timeout': endpoint.timeout}
            self.field_mapping=goassoc_fieldmap(self.relationship_type)

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
                if cc is not None and object is None:
                    object = cc

        self.update_solr_url(**solr_config)

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
            p = (subject_category, object_category)
            if p == ('disease', 'gene'):
                self.invert_subject_object = True
            elif p == ('disease', 'model'):
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

        # We want to match all associations that have either a subject or object
        # with an ID that is contained in subject_or_object_ids.
        if subject_or_object_ids is not None:
            quotified_ids = solr_quotify(subject_or_object_ids)
            subject_id_filter = '{}:{}'.format('subject_closure', quotified_ids)
            object_id_filter = '{}:{}'.format('object_closure', quotified_ids)

            # If subject_or_object_category is provided, we add it to the filter.
            if self.subject_or_object_category is not None:
                quotified_categories = solr_quotify(self.subject_or_object_category)
                subject_category_filter = '{}:{}'.format('subject_category', quotified_categories)
                object_category_filter = '{}:{}'.format('object_category', quotified_categories)

                filter_queries.append(
                    '(' + subject_id_filter + ' AND ' + object_category_filter + ')' \
                    ' OR '                                                      \
                    '(' + object_id_filter + ' AND ' + subject_category_filter + ')'
                )

            else:
                filter_queries.append(subject_id_filter + ' OR ' + object_id_filter)

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

        if self._use_amigo_schema:
            select_fields += [x for x in M.AMIGO_SPECIFIC_FIELDS if x not in select_fields]

        ## true if iterate in windows of max_size until all results found
        iterate=self.iterate

        #logging.info('FL'+str(select_fields))
        is_unlimited = False
        rows=self.rows
        if rows < 0:
            is_unlimited = True
            iterate = True
            rows = self.max_rows

        for field in self.non_null_fields:
            filter_queries.append(field + ":['' TO *]")

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

        if self.start is not None:
            params['start'] = self.start

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
                next_results = self.solr.search(start=start, **params)
                next_docs = next_results.docs
                n_docs = len(next_docs)
                docs += next_docs
                start += self.rows
            results.docs = docs

        fcs = results.facets

        payload = {
            'facet_counts': translate_facet_field(fcs, self.invert_subject_object),
            'pagination': {},
            'numFound': results.hits
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
            for field in INVERT_FIELDS_MAP:
                flip(d, field, INVERT_FIELDS_MAP[field])

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

        if self.invert_subject_object and assoc['relation'] is not None:
            assoc['relation']['inverse'] = True

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
            assoc['types'] = [t for t in d[M.EVIDENCE_OBJECT] if t.startswith('ECO:')]

        if self._use_amigo_schema:
            for f in M.AMIGO_SPECIFIC_FIELDS:
                if f in d:
                    assoc[f] = d[f]

        # solr does not allow nested objects, so evidence graph is json-encoded
        if M.EVIDENCE_GRAPH in d:
            assoc[M.EVIDENCE_GRAPH] = json.loads(d[M.EVIDENCE_GRAPH])
        return assoc

    def translate_docs(self, ds, **kwargs):
        """
        Translate a set of solr results
        """
        for d in ds:
            self.map_doc(d, {}, self.invert_subject_object)

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





### This may quite possibly be a temporary code, but it looks a lot simpler than the above for more customizable Solr queries
import requests
from enum import Enum


## Should take those URLs from config.yaml
class ESOLR(Enum):
    GOLR = "http://golr-aux.geneontology.io/solr/"
    MOLR = "https://solr.monarchinitiative.org/solr/search"

class ESOLRDoc(Enum):
    ONTOLOGY = "ontology_class"
    ANNOTATION = "annotation"
    BIOENTITY = "bioentity"

## Respect the method name for run_sparql_on with enums
def run_solr_on(solrInstance, category, id, fields):
    """
    Return the result of a solr query on the given solrInstance (Enum ESOLR), for a certain document_category (ESOLRDoc) and id
    """
    query = solrInstance.value + "select?q=*:*&fq=document_category:\"" + category.value + "\"&fq=id:\"" + id + "\"&fl=" + fields + "&wt=json&indent=on"
    response = requests.get(query)
    return response.json()['response']['docs'][0]

def run_solr_text_on(solrInstance, category, q, qf, fields, optionals):
    """
    Return the result of a solr query on the given solrInstance (Enum ESOLR), for a certain document_category (ESOLRDoc) and id
    """
    if optionals == None:
        optionals = ""
    query = solrInstance.value + "select?q=" + q + "&qf=" + qf + "&fq=document_category:\"" + category.value + "\"&fl=" + fields + "&wt=json&indent=on" + optionals
    # print("QUERY: ", query)

    response = requests.get(query)
    return response.json()['response']['docs']


### Those utility functions should find their place in a common utils.py if any exists

## Utility function to merge two field of a json
def merge(json, firstField, secondField):
    """
    merge two fields of a json into an array of { firstField : secondField }
    """
    merged = []

    for i in range(0, len(json[firstField])):
        merged.append({ json[firstField][i] : json[secondField][i] })
    return merged
    
## Utility function to filter out two fields of a json and give it each a new label
def mergeWithLabels(json, firstField, firstFieldLabel, secondField, secondFieldLabel):
    """
    merge two fields of a json into an array of { firstFieldLabel : firstFieldLabel, secondFieldLabel : secondField }
    """
    merged = []

    for i in range(0, len(json[firstField])):
        merged.append({ firstFieldLabel : json[firstField][i],
                        secondFieldLabel : json[secondField][i] })
    return merged

## Utility function to replace in a specific <field> an <old> string by a <new> string
def replace(json, field, old, new):
    for i in range(0, len(json)):
        if json[i][field]:
            json[i][field] = json[i][field].replace(old, new)
    return json