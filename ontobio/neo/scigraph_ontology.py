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

class RemoteScigraphOntology(Ontology):
    """
    ontology backed by SciGraph endpoint
    """

    def __init__(self, url=None):
        if url is not None:
            self.url_prefix = url
        else:
            self.url_prefix = "http://scigraph-data.monarchinitiative.org/scigraph/"
        return
    
    # Internal wrapper onto requests API
    def get_response(self, path="", q=None, format=None, **params):
        url = self.url_prefix + path;
        if q is not None:
            url += "/" +q;
        if format is not None:
            url = url  + "." + format;
        r = requests.get(url, params=params)
        return r

    def neighbors(self, id=None, **params):
        """
        Get neighbors of a node

        parameters are directly passed through to SciGraph: e.g. depth, relationshipType
        """
        response = self.get_response("graph/neighbors", id, "json", **params)
        # TODO: should return ids?
        return response.json()
    
    def extract_subset(self, subset):
        pass
    
    def resolve_names(self, names, is_remote=False, **args):
        ## TODO
        return names
    
    def subgraph(self, nodes=[]):
        return self.get_graph().subgraph(nodes)

    
