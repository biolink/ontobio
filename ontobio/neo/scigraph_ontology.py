"""
Classes for representing ontologies backed by SciGraph endpoint

E.g.
https://scigraph-ontology.monarchinitiative.org/scigraph/docs/#!/graph/getNeighbors
"""

import networkx as nx
import logging
import ontobio.ontol
import requests
from ontobio.ontol import Ontology
from ontobio.util.user_agent import get_user_agent

class RemoteScigraphOntology(Ontology):
    """
    ontology backed by SciGraph endpoint.

    This class implements a subset of the methods in `Ontology`, 
    it should be able to substitute for an Ontology method
    """

    def __init__(self,
                 handle=None,
                 url=None,
                 config=None):
        """
        Constructor - typically you do not need to call this directly.

        Specify a scigraph handle in ontol_factory, e.g.

        ``
        OntologyFactory().create('scigraph:data')
        ``

        The Session instance will be consulted to determine the URL

        The handle can be

        - `scigraph:ontology` use scigraph_ontology from config
        - `scigraph:data` use scigraph_data from config
        - `scigraph:` use default
        """
        if handle is not None:
            handle = handle.replace("scigraph:","")
        else:
            handle = "ontology"

        logging.info("Connecting: {} {}".format(handle, url))
        if url is None:
            if config is None:
                from ontobio.config import get_config
                config = get_config()
            if config is not None:
                logging.info("Fetching scigraph URL from config: {}".format(handle))                
                urlObj = config.scigraph_ontology
                if handle == 'data':
                    logging.info("Using scigraph_data URL")
                    urlObj = config.scigraph_data
                if urlObj is not None:
                    url = urlObj.url
                    logging.info("Set URL from config={} {}".format(url, urlObj))
            if url is None:
                url = 'https://scigraph-ontology.monarchinitiative.org/scigraph'
        self.url = url
        logging.info("Base SciGraph URL: {}".format(url))
        return

    # Internal wrapper onto requests API
    def _get_response(self, path="", q=None, format=None, **params):
        url = self.url
        if not url.endswith("/"):
            url += "/"
        url += path
        if q is not None:
            url += "/" +q
        if format is not None:
            url = url  + "." + format
        r = requests.get(url, params=params, headers={'User-Agent': get_user_agent(modules=[requests], caller_name=__name__)})
        return r

    def _get_response_json(self, path="", q=None, format=None, **args):
        r = self._get_response(path, q, format, **args)
        if r.status_code == 200:
            return r.json()
        else:
            return []
    
    def _neighbors_graph(self, id=None, **params):
        """
        Get neighbors of a node

        parameters are directly passed through to SciGraph: e.g. depth, relationshipType
        """
        response = self._get_response("graph/neighbors", id, "json", **params)
        return response.json()

    # Override
    def subgraph(self, nodes=None, relations=None):
        if nodes is None:
            nodes = []
        r_nodes = []
        r_edges = []
        
        logging.debug("Scigraph, Subgraph for {}".format(nodes))
        for n in nodes:
            logging.debug("Parents-of {}".format(n))
            g = self._neighbors_graph(n,
                                      direction='OUTGOING',
                                      depth=1,
                                      relationshipType=self._mkrel(relations))
            r_nodes += g['nodes']
            r_edges += g['edges']
        digraph = nx.MultiDiGraph()
        for n in r_nodes:
            digraph.add_node(n['id'], attr_dict=self._repair(n))
        for e in r_edges:
            digraph.add_edge(e['obj'],e['sub'], pred=e['pred'])
        return digraph


    # Override
    def subontology(self, nodes, **args):
        if nodes is None:
            nodes = []
        g = self.subgraph(nodes, **args)
        ont = Ontology(graph=g) 
        return ont

    # Override
    # TODO: dependent on modeling in scigraph
    def subsets(self, nid, contract=True):
        raise NotImplementedError()

    def get_roots(self, relations=None, prefix=None):
        raise NotImplementedError()
    
    # Override
    # Override
    def nodes(self):
        raise NotImplementedError()

    def _mkrel(self, relations=None):
        if relations is not None:
            return "|".join(relations)
        else:
            return None

        
    # Override
    def ancestors(self, node, relations=None, reflexive=False):
        logging.debug("Ancestors of {} over {}".format(node, relations))
        g = self._neighbors_graph(node,
                                  direction='OUTGOING',
                                  depth=20,
                                  relationshipType=self._mkrel(relations))
        arr = [v['id'] for v in g['nodes']]
        if reflexive:
            arr.add(node)
        else:
            if node in arr:
                arr.remove(node)
        return arr

    # Override
    def descendants(self, node, relations=None, reflexive=False):
        logging.debug("Descendants of {} over {}".format(node, relations))
        g = self._neighbors_graph(node,
                                  direction='INCOMING',
                                  depth=20,
                                  relationshipType=self._mkrel(relations))
        arr = [v['id'] for v in g['nodes']]
        if reflexive:
            arr.add(node)
        else:
            if node in arr:
                arr.remove(node)
        return arr
    
    # Override
    def neighbors(self, node, relations=None):
        g = self._neighbors_graph(node,
                                  direction='BOTH',
                                  depth=1,
                                  relationshipType=self._mkrel(relations))
        return [v['id'] for v in g['nodes']]

    # map between bbopgraph and obograph
    def _repair(self, n):
        if 'lbl' in n:
            n['label'] = n['lbl']
            del n['lbl']
        # TODO: transform meta
        return n
            
    # Override
    def node(self, nid):
        g = self._neighbors_graph(nid,
                                  depth=0)
        return self._repair(g['nodes'][0])

    # Override
    def has_node(self, id):
        return self.node(id) is not None

    # Override
    def traverse_nodes(self, qids, up=True, down=False, relations=None):
        nodes = set()
        for id in qids:
            # reflexive - always add self
            nodes.add(id)
            if down:
                nodes.update(self.descendants(id, relations=relations))
            if up:
                nodes.update(self.ancestors(id, relations=relations))
        return nodes
    
    def label(self, nid, id_if_null=False):
        n = self.node(nid)
        if n is not None and 'label' in n:
            return n['label']
        else:
            if id_if_null:
                return nid
            else:
                return None
    
    def extract_subset(self, subset):
        raise NotImplementedError()

    # Override
    def resolve_names(self, names, synonyms=True, **args):
        results = set()
        for name in names:
            for r in self._vocab_search(name, searchSynonyms=synonyms):
                logging.debug("RESULT={}".format(r))
                results.add(r['curie'])
        logging.debug("Search {} -> {}".format(names, results))
        return list(results)

    # this uses one of two routes depending on whether exact or inexact
    # matching is required
    def _vocab_search(self, term, **args):
        if '%' in term:
            term = term.replace('%','')
            return self._get_response_json("vocabulary/search", term, "json", **args)
        else:
            return self._get_response_json("vocabulary/term", term, "json", **args)
    

    
