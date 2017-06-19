"""
Reconsitutes an ontology from SPARQL queries over a remote SPARQL server

 * the first time an ontology is referenced, basic axioms will be fetched via SPARQL
 * these will be cached in `/tmp/.cache/`
 * the second time the same ontology is referenced, the disk cache will be used
 * if an ontology is referenced a second time in the same in-memory session, the disk cache is bypassed and in-memory (lru) cache is used

Note: you should not need to use this directly. An `OntologyFactory` object will automatically use this if a sparql handle is passed.

"""

from SPARQLWrapper import SPARQLWrapper, JSON
from prefixcommons.curie_util import contract_uri, expand_uri
from functools import lru_cache
import networkx
from cachier import cachier
import datetime
import logging

SHELF_LIFE = datetime.timedelta(days=7)

# CACHE STRATEGY:
# by default, the cache is NOT persistent. Only single threaded clients should
# call a cached method with writecache=True.
# Note we are layering the in-memory cache over the persistent cache

cache = lru_cache(maxsize=None)
#cache = cachier(stale_after=SHELF_LIFE)


SUBCLASS_OF = 'subClassOf'
SUBPROPERTY_OF = 'subPropertyOf'

# TODO
# for now we assume ontobee
ontol_sources = {
    'go': "http://rdf.geneontology.org/sparql",
    '': "http://sparql.hegroup.org/sparql"
    }

OIO_SYNS = dict(
    related='oboInOwl:hasRelatedSynonym',
    narrow = 'oboInOwl:hasNarrowSynonym',
    broad = 'oboInOwl:hasBroadSynonym',
    exact = 'oboInOwl:hasExactSynonym')
    

def get_digraph(ont, relations=None, writecache=False):
    """
    Creates a basic graph object corresponding to a remote ontology
    """
    digraph = networkx.MultiDiGraph()
    for (s,p,o) in get_edges(ont):
        if relations is None or p in relations:
            digraph.add_edge(o,s,pred=p)
    for (n,label) in fetchall_labels(ont):
        digraph.add_node(n, attr_dict={'label':label})
    return digraph

def get_xref_graph(ont):
    """
    Creates a basic graph object corresponding to a remote ontology
    """
    g = networkx.MultiGraph()
    for (c,x) in fetchall_xrefs(ont):
        g.add_edge(c,x,source=c)
    return g


@cachier(stale_after=SHELF_LIFE)
def get_edges(ont):
    """
    Fetches all basic edges from a remote ontology
    """
    logging.info("QUERYING:"+ont)
    edges = [(c,SUBCLASS_OF, d) for (c,d) in fetchall_isa(ont)]
    edges += fetchall_svf(ont)
    edges += [(c,SUBPROPERTY_OF, d) for (c,d) in fetchall_subPropertyOf(ont)]
    if len(edges) == 0:
        logging.warn("No edges for {}".format(ont))
    return edges

def search(ont, searchterm):
    """
    Search for things using labels
    """
    namedGraph = get_named_graph(ont)
    query = """
    SELECT ?c ?l WHERE {{
    GRAPH <{g}>  {{
    ?c rdfs:label ?l
    FILTER regex(?l,'{s}','i')
    }}
    }}
    """.format(s=searchterm, g=namedGraph)
    bindings = run_sparql(query)
    return [(r['c']['value'],r['l']['value']) for r in bindings]

@cachier(stale_after=SHELF_LIFE)
def get_terms_in_subset(ont, subset):
    """
    Find all nodes in a subset.

    We assume the oboInOwl encoding of subsets, and subset IDs are IRIs
    """
    namedGraph = get_named_graph(ont)

    # note subsets have an unusual encoding
    query = """
    prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
    SELECT ?c ? WHERE {{
    GRAPH <{g}>  {{
    ?c oboInOwl:inSubset ?s ;
       rdfs:label ?l
    FILTER regex(?s,'#{s}$','i')
    }}
    }}
    """.format(s=subset, g=namedGraph)
    bindings = run_sparql(query)
    return [(r['c']['value'],r['l']['value']) for r in bindings]


def run_sparql(q):
    # TODO: select endpoint based on ontology
    #sparql = SPARQLWrapper("http://rdf.geneontology.org/sparql")
    logging.info("Connecting to sparql endpoint...")
    sparql = SPARQLWrapper("http://sparql.hegroup.org/sparql")
    logging.info("Made wrapper: {}".format(sparql))
    # TODO: iterate over large sets?
    full_q = q + ' LIMIT 250000'
    sparql.setQuery(q)
    sparql.setReturnFormat(JSON)
    logging.info("Query: {}".format(q))
    results = sparql.query().convert()
    bindings = results['results']['bindings']
    logging.info("Rows: {}".format(len(bindings)))
    for r in bindings:
        curiefy(r)
    return bindings


def curiefy(r):
    for (k,v) in r.items():
        if v['type'] == 'uri':
            curies = contract_uri(v['value'])
            if len(curies)>0:
                r[k]['value'] = curies[0]
                
def get_named_graph(ont):
    """
    Ontobee uses NGs such as http://purl.obolibrary.org/obo/merged/CL
    """

    if ont.startswith('http://'):
        return ont
    namedGraph = 'http://purl.obolibrary.org/obo/merged/' + ont.upper()
    return namedGraph

def fetchall_isa(ont):
    namedGraph = get_named_graph(ont)
    queryBody = querybody_isa()
    query = """
    SELECT * WHERE {{
    GRAPH <{g}>  {q}
    }}
    """.format(q=queryBody, g=namedGraph)
    bindings = run_sparql(query)
    return [(r['c']['value'],r['d']['value']) for r in bindings]

def fetchall_subPropertyOf(ont):
    namedGraph = get_named_graph(ont)
    queryBody = querybody_subPropertyOf()
    query = """
    SELECT * WHERE {{
    GRAPH <{g}>  {q}
    }}
    """.format(q=queryBody, g=namedGraph)
    bindings = run_sparql(query)
    return [(r['c']['value'],r['d']['value']) for r in bindings]

def fetchall_svf(ont):
    namedGraph = get_named_graph(ont)
    queryBody = querybody_svf()
    query = """
    SELECT * WHERE {{
    GRAPH <{g}>  {q}
    }}
    """.format(q=queryBody, g=namedGraph)
    bindings = run_sparql(query)
    return [(r['c']['value'], r['p']['value'], r['d']['value']) for r in bindings]

@cachier(stale_after=SHELF_LIFE)
def fetchall_labels(ont):
    """
    fetch all rdfs:label assertions for an ontology
    """
    logging.info("fetching rdfs:labels for: "+ont)
    namedGraph = get_named_graph(ont)
    queryBody = querybody_label()
    query = """
    SELECT * WHERE {{
    GRAPH <{g}>  {q}
    }}
    """.format(q=queryBody, g=namedGraph)
    bindings = run_sparql(query)
    rows = [(r['c']['value'], r['l']['value']) for r in bindings]
    return rows

@cachier(stale_after=SHELF_LIFE)
def fetchall_syns(ont):
    """
    fetch all synonyms for an ontology
    """
    logging.info("fetching syns for: "+ont)
    namedGraph = get_named_graph(ont)
    queryBody = querybody_syns()
    query = """
    prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
    SELECT * WHERE {{
    GRAPH <{g}>  {q}
    }}
    """.format(q=queryBody, g=namedGraph)
    bindings = run_sparql(query)
    rows = [(r['c']['value'], r['r']['value'], r['l']['value']) for r in bindings]
    return rows

@cachier(stale_after=SHELF_LIFE)
def fetchall_text_defs(ont):
    """
    fetch all text defs for an ontology
    """
    logging.info("fetching text defs for: "+ont)
    namedGraph = get_named_graph(ont)
    query = """
    prefix IAO: <http://purl.obolibrary.org/obo/IAO_>
    SELECT * WHERE {{
    GRAPH <{g}>  {{
      ?c IAO:0000115 ?d
    }}
    }}
    """.format(g=namedGraph)
    bindings = run_sparql(query)
    rows = [(r['c']['value'], r['d']['value']) for r in bindings]
    return rows

@cachier(stale_after=SHELF_LIFE)
def fetchall_xrefs(ont):
    """
    fetch all xrefs for an ontology
    """
    logging.info("fetching xrefs for: "+ont)
    namedGraph = get_named_graph(ont)
    query = """
    prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
    SELECT * WHERE {{
    GRAPH <{g}>  {{ ?c oboInOwl:hasDbXref ?x }}
    }}
    """.format(g=namedGraph)
    bindings = run_sparql(query)
    rows = [(r['c']['value'], r['x']['value']) for r in bindings]
    return rows

def querybody_isa():
    return """
    { ?c rdfs:subClassOf ?d }
    FILTER (!isBlank(?c))
    FILTER (!isBlank(?d))
    """

def querybody_subPropertyOf():
    return """
    { ?c rdfs:subPropertyOf ?d }
    FILTER (!isBlank(?c))
    FILTER (!isBlank(?d))
    """

def querybody_svf():
    return """
    { ?c rdfs:subClassOf [owl:onProperty ?p ; owl:someValuesFrom ?d ] }
    FILTER (!isBlank(?c))
    FILTER (!isBlank(?p))
    FILTER (!isBlank(?d))
    """

def querybody_label():
    return """
    { ?c rdfs:label ?l }
    """

def querybody_syns():
    return """
    { ?c ?r ?l }
    FILTER (
    ?r = oboInOwl:hasRelatedSynonym OR
    ?r = oboInOwl:hasNarrowSynonym OR
    ?r = oboInOwl:hasBroadSynonym OR
    ?r = oboInOwl:hasExactSynonym
    )
    """

def anyont_fetch_label(id):
    """
    fetch all rdfs:label assertions for a URI
    """
    iri = expand_uri(id, strict=False)
    query = """
    SELECT ?label WHERE {{
    <{iri}> rdfs:label ?label
    }}
    """.format(iri=iri)
    bindings = run_sparql(query)
    rows = [r['label']['value'] for r in bindings]
    return rows[0]

def batch_fetch_labels(ids):
    """
    fetch all rdfs:label assertions for a set of CURIEs
    """
    m = {}
    for id in ids:
        label = anyont_fetch_label(id)
        if label is not None:
            m[id] = label
    return m

## -- PERSISTENCE --


