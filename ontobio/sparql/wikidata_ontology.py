"""
An ontology backed by a remote Wikidata SPARQL service.
"""

import networkx as nx
import logging
import ontobio.ontol
from ontobio.ontol import Ontology, Synonym
from prefixcommons.curie_util import contract_uri, expand_uri, get_prefixes
from SPARQLWrapper import SPARQLWrapper, JSON, RDF
from ontobio.sparql.rdflib_bridge import rdfgraph_to_ontol
from ontobio.sparql.sparql_ontol_utils import OIO_SYNS, get_named_graph, run_sparql

class WikidataOntology(Ontology):
    """
    An ontology backed by a remote Wikidata SPARQL service.
    """


    # TODO
    # Override
    def resolve_names(self, names, is_remote=False, synonyms=False, **args):
        if not is_remote:
            # TODO: ensure synonyms present
            return super().resolve_names(names, **args)
        else:
            results = set()
            for name in names:
                results.update( self._search(name, 'rdfs:label', **args) )
                if synonyms:
                    for pred in OIO_SYNS.values():
                        results.update( self._search(name, pred, **args) )
            logging.info("REMOTE RESULTS="+str(results))
            return list(results)

    # TODO
    def _search(self, searchterm, pred, **args):
        """
        Search for things using labels
        """
        # TODO: DRY with sparql_ontol_utils
        searchterm = searchterm.replace('%','.*')
        namedGraph = get_named_graph(self.handle)
        query = """
        prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
        SELECT ?c WHERE {{
        GRAPH <{g}>  {{
        ?c {pred} ?l
        FILTER regex(?l,'{s}','i')
        }}
        }}
        """.format(pred=pred, s=searchterm, g=namedGraph)
        bindings = run_sparql(query)
        return [r['c']['value'] for r in bindings]

    # TODO
    def sparql(self, select='*', body=None, inject_prefixes=None, single_column=False):
        """
        Execute a SPARQL query.

        The query is specified using `select` and `body` parameters.
        The argument for the Named Graph is injected into the query.

        The select parameter should be either '*' or a list of vars (not prefixed with '?').

         - If '*' is passed, then the result is a list of dicts, { $var: {value: $val } }
         - If a list of vars is passed, then the result is a list of lists
         - Unless single_column=True, in which case the results are a simple list of values from the first var

        The inject_prefixes argument can be used to inject a list of prefixes - these are expanded
        using the prefixcommons library
        
        """
        if inject_prefixes is None:
            inject_prefixes = []
        namedGraph = get_named_graph(self.handle)
        cols = []
        select_val = None
        if select is None or select=='*':
            if not single_column:
                cols=None
            select_val='*'
        else:
            if isinstance(cols,list):
                cols = [select]
            else:
                cols = select
            select_val = ", ".join(['?'+c for c in cols])

        prefixes = ""
        if inject_prefixes is not None:
            plist = ["prefix {}: <{}> ".format(p,expand_uri(p+":")) for p in inject_prefixes if p != "" and p is not None]
            prefixes = "\n".join(plist)
        query = """
        {prefixes}
        SELECT {s} WHERE {{
        GRAPH <{g}>  {{
        {b}
        }}
        }}
        """.format(prefixes=prefixes, s=select_val, b=body, g=namedGraph)
        bindings = run_sparql(query)
        if len(bindings) == 0:
            return []
        if cols is None:
            return bindings
        else:
            if single_column:
                c = list(bindings[0].keys())[0]
                return [r[c]['value'] for r in bindings]
            else:
                return [r[c]['value'] for c in cols for r in bindings]
    
    
class EagerWikidataOntology(WikidataOntology):
    """
    Eager Wikidata ontology implementation.

    Caches all classes that are sub or super classes of a specified node
    """

    def __init__(self, handle=None):
        """
        initializes based on an ontology class ID (Q ID) in wikidata
        """
        handle = handle.replace('wdq:','')
        self.handle = handle
        logging.info("Creating eager-wikidata-ont from "+str(handle))
        self.create_from_hub(handle)

    def __str__(self):
        return "h:{} g:{}".format(self.handle, self.graph)

    def create_from_hub(self, hub_id):
        if hub_id.find(":") == -1:
            hub_id = 'wd:' + hub_id
        if hub_id.startswith('http'):
            hub_id = '<' + hub_id + '>'
        q = """
        PREFIX wd: <http://www.wikidata.org/entity/> 
        CONSTRUCT {{
        ?cls rdfs:label ?clsLabel .
        ?cls a owl:Class .
        ?superClass a owl:Class .
        ?superClass rdfs:label ?superClassLabel .
        ?cls rdfs:subClassOf ?superClass
        }}
        WHERE {{
         {{  {{ ?cls wdt:P279* {hub_id} }} UNION
             {{ {hub_id} wdt:P279* ?cls }} }}
        ?cls wdt:P279 ?superClass
        SERVICE wikibase:label {{
          bd:serviceParam wikibase:language "en" .
        }}
        }}
        """.format(hub_id=hub_id)
        logging.info("QUER={}".format(q))
        sparql = SPARQLWrapper("http://query.wikidata.org/sparql")
        sparql.setQuery(q)
        sparql.setReturnFormat(RDF)
        rg = sparql.query().convert()
        logging.info("RG={}".format(rg))
        ont = rdfgraph_to_ontol(rg)
        self.graph = ont.graph
        

class LazyWikidataOntology(WikidataOntology):
    """
    Non-caching wikidata-backed ontology TODO
    """

    def __init__(self):
        self.all_logical_definitions = [] ## TODO


    
