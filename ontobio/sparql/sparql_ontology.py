"""
Classes for representing ontologies backed by a SPARQL endpoint
"""

import networkx as nx
import logging
import ontobio.ontol
from ontobio.ontol import Ontology, Synonym
from ontobio.sparql.sparql_ontol_utils import get_digraph, get_named_graph, get_xref_graph, run_sparql, fetchall_syns, fetchall_labels


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

    def all_synonyms(self, include_label=False):
        syntups = fetchall_syns(self.graph_name)
        syns = [Synonym(t[0],pred=t[1], val=t[2]) for t in syntups]
        if include_label:
            #lsyns = [Synonym(t[0],pred='label', val=t[1]) for t in fetchall_labels(self.graph_name)]
            lsyns = [Synonym(x, pred='label', val=self.label(x)) for x in self.nodes()]
            syns = syns + lsyns
        return syns
    
    def resolve_names(self, names, is_remote=False, **args):
        if not is_remote:
            return super().resolve_names(names, **args)
        else:
            results = []
            for name in names:
                results += self._search(name)
            logging.info("REMOT RESULTS="+str(results))
            return results
        
    def _search(self, searchterm):
        """
        Search for things using labels
        """
        # TODO: DRY with sparql_ontol_utils
        searchterm = searchterm.replace('%','.*')
        namedGraph = get_named_graph(self.handle)
        query = """
        SELECT ?c WHERE {{
        GRAPH <{g}>  {{
        ?c rdfs:label ?l
        FILTER regex(?l,'{s}','i')
        }}
        }}
        """.format(s=searchterm, g=namedGraph)
        bindings = run_sparql(query)
        return [r['c']['value'] for r in bindings]

    def sparql(self, select='*', body=None, single_column=False):
        """
        Execute a SPARQL query.

        The query is specified using `select` and `body` parameters.
        The argument for the Named Graph is injected into the query.

        The select parameter should be either '*' or a list of vars (not prefixed with '?').

         - If '*' is passed, then the result is a list of dicts, { $var: {value: $val } }
         - If a list of vars is passed, then the result is a list of lists
         - Unless single_column=True, in which case the results are a simple list of values from the first var
        
        """
        namedGraph = get_named_graph(self.handle)
        cols = []
        select_val = None
        if select is None or select=='*':
            cols=None
            select_val='*'
        else:
            cols = select
            select_val = ", ".join(['?'+c for c in select])
        query = """
        SELECT {s} WHERE {{
        GRAPH <{g}>  {{
        {b}
        }}
        }}
        """.format(s=select_val, b=body, g=namedGraph)
        bindings = run_sparql(query)
        if cols == None:
            return bindings
        else:
            if single_column:
                c = cols[0]
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
        self.graph = g
        self.graph_name = get_named_graph(handle)
        self.xref_graph = get_xref_graph(handle)
        logging.info("Graph "+str(self.graph))

    def __str__(self):
        return "h:{} g:{}".format(self.handle, self.graph)




class LazyRemoteSparqlOntology(RemoteSparqlOntology):
    """
    Local or remote ontology
    """

    def __init__(self):
        pass

    
