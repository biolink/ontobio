"""
Classes for representing ontologies backed by a SPARQL endpoint
"""

import networkx as nx
import logging
import ontobio.ontol
from ontobio.ontol import Ontology, Synonym
from ontobio.sparql.sparql_ontol_utils import get_digraph, get_named_graph, get_xref_graph, run_sparql, fetchall_syns, fetchall_labels, OIO_SYNS
from prefixcommons.curie_util import contract_uri, expand_uri, get_prefixes


class RemoteSparqlOntology(Ontology):
    """
    Local or remote ontology
    """

    def extract_subset(self, subset):
        """
        Find all nodes in a subset.
    
        We assume the oboInOwl encoding of subsets, and subset IDs are IRIs
        """
    
        # note subsets have an unusual encoding
        query = """
        prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
        SELECT ?c WHERE {{
        GRAPH <{g}>  {{
        ?c oboInOwl:inSubset ?s
        FILTER regex(?s,'#{s}$','i')
        }}
        }}
        """.format(s=subset, g=self.graph_name)
        bindings = run_sparql(query)
        return [r['c']['value'] for r in bindings]

    def subsets(self):
        """
        Find all subsets for an ontology
        """
    
        # note subsets have an unusual encoding
        query = """
        prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#>
        SELECT DISTINCT ?s WHERE {{
        GRAPH <{g}>  {{
        ?c oboInOwl:inSubset ?s 
        }}
        }}
        """.format(g=self.graph_name)
        bindings = run_sparql(query)
        return [r['s']['value'] for r in bindings]

    def synonyms(self, nid, **args):
        logging.info("lookup syns for {}".format(nid))
        if self.all_synonyms_cache == None:
            self.all_synonyms()
        return super().synonyms(nid, **args) 
    
    # Override
    def all_synonyms(self, include_label=False):
        logging.debug("Fetching all syns...")
        # TODO: include_label in cache
        if self.all_synonyms_cache == None:
            syntups = fetchall_syns(self.graph_name)
            syns = [Synonym(t[0],pred=t[1], val=t[2]) for t in syntups]
            for syn in syns:
                self.add_synonym(syn)
            if include_label:
                #lsyns = [Synonym(t[0],pred='label', val=t[1]) for t in fetchall_labels(self.graph_name)]
                lsyns = [Synonym(x, pred='label', val=self.label(x)) for x in self.nodes()]
                syns = syns + lsyns
            self.all_synonyms_cache = syns
        return self.all_synonyms_cache

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

    def sparql(self, select='*', body=None, inject_prefixes=[], single_column=False):
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
        if cols == None:
            return bindings
        else:
            if single_column:
                c = list(bindings[0].keys())[0]
                return [r[c]['value'] for r in bindings]
            else:
                return [r[c]['value'] for c in cols for r in bindings]
    
    
class EagerRemoteSparqlOntology(RemoteSparqlOntology):
    """
    Local or remote ontology
    """

    def __init__(self, handle=None):
        """
        initializes based on an ontology name
        """
        self.handle = handle
        logging.info("Creating eager-remote-sparql from "+str(handle))
        g = get_digraph(handle, None, True)
        logging.info("Graph:"+str(g))
        if len(g.nodes()) == 0 and len(g.edges()) == 0:
            logging.error("Empty graph for '{}' - did you use the correct id?".
                          format(handle))
        self.graph = g
        self.graph_name = get_named_graph(handle)
        self.xref_graph = get_xref_graph(handle)
        self.all_logical_definitions = []
        self.all_synonyms_cache = None
        logging.info("Graph: {} LDs: {}".format(self.graph, self.all_logical_definitions))

    def __str__(self):
        return "h:{} g:{}".format(self.handle, self.graph)




class LazyRemoteSparqlOntology(RemoteSparqlOntology):
    """
    Local or remote ontology
    """

    def __init__(self):
        self.all_logical_definitions = [] ## TODO


    
