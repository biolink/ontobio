"""
BBOP Graph class created in the original biolink-api
before ontobio was stripped out, it is still used
in the scigraph-util

TODO Merge this with OBOGraph
"""
from typing import Dict


class BBOPGraph:

    """
    BBOPGraph Graph object model
    https://github.com/berkeleybop/bbop-graph
    """

    nodemap = {}

    def __init__(self, obj: Dict = None):
        obj = obj or {}
        self.nodes = []
        self.edges = []
        if obj:
            self.add_json_graph(obj)

    def add_json_graph(self, obj):
        for node in obj['nodes']:
            self.add_node(Node(**node))
        for edge in obj['edges']:
            self.add_edge(Edge(edge))

    def add_node(self, node) :
        self.nodemap[node.id] = node
        self.nodes.append(node)

    def add_edge(self, edge) :
        self.edges.append(edge)

    def merge(self, graph):
        for node in graph.nodes:
            self.add_node(node)
        for edge in graph.edges:
            self.add_edge(edge)

    def get_node(self, id):
        return self.nodemap[id]

    def get_lbl(self, id):
        return self.nodemap[id].lbl

    def get_root_nodes(self, relations):
        roots = []
        if relations is None:
            relations = []
        for node in self.nodes:
            if len(self.get_outgoing_edges(node.id, relations)) == 0:
                roots.append(node)
        return roots

    def get_leaf_nodes(self, relations):
        roots = []
        if relations is None:
            relations = []
        for node in self.nodes:
            if len(self.get_incoming_edges(node.id, relations)) == 0:
                roots.append(node)
        return roots

    def get_outgoing_edges(self, nid, relations):
        el = []
        if relations is None:
            relations = []
        for edge in self.edges:
            if edge.sub == nid:
                if len(relations) == 0 or edge.pred in relations:
                    el.append(edge)
        return el

    def get_incoming_edges(self, nid, relations=[]):
        el = []
        for edge in self.edges:
            if edge.obj == nid:
                if len(relations) == 0 or edge.pred in relations:
                    el.append(edge)
        return el

    def as_dict(self):
        return {
            "nodes": [node.as_dict() for node in self.nodes],
            "edges": self.edges
        }


class Node:
    def __init__(self, id, lbl=None, meta=None):    
        self.id = id
        self.lbl = lbl
        self.meta = Meta(meta)

    def __str__(self):
        return self.id + ' "' + str(self.lbl) + '"'

    def as_dict(self):
        return {
            "id": self.id,
            "lbl": self.lbl,
            "meta": self.meta.pmap
        }


class Edge:
    def __init__(self, obj):
        self.sub = obj['sub']
        self.pred = obj['pred']
        self.obj = obj['obj']
        self.meta = obj['meta']
    
    def __str__(self):
        return self.sub + "-[" + self.pred + "]->" + self.obj


class Meta:
    def __init__(self, obj):
        self.type_list = obj['types']
        self.category_list = []
        if 'category' in obj:
            self.category_list = obj['category']
        self.pmap = obj
