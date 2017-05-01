"""
A module for representing simple graph-oriented views of an ontology

See also:

 - ontol_factory.py

"""

import networkx as nx
import logging
import re

class Ontology():
    """An object that represents a basic graph-oriented view over an ontology.

    The ontology may be represented in memory, or it may be located
    remotely. See subclasses for details.

    The default implementation is an in-memory wrapper onto the python networkx library

    """

    def __init__(self, handle=None, graph=None, xref_graph=None, payload=None, graphdoc=None):
        """
        initializes based on an ontology name.

        Note: do not call this directly, use OntologyFactory instead
        """
        self.handle = handle

        # networkx object
        self.graph = graph
        self.xref_graph = xref_graph

        # obograph
        self.graphdoc = graphdoc

        # alternatively accept a payload object
        if payload is not None:
            self.graph = payload.get('graph')
            self.xref_graph = payload.get('xref_graph')
            self.graphdoc = payload.get('graphdoc')
            self.all_logical_definitions = payload.get('logical_definitions')
        

    def get_graph(self):
        """
        Returns a networkx graph for the whole ontology.

        Only implemented for 'eager' implementations 
        """
        return self.graph

    # consider caching
    def get_filtered_graph(self, relations=None, prefix=None):
        """
        Returns a networkx graph for the whole ontology, for a subset of relations

        Only implemented for eager methods.

        Implementation notes: currently this is not cached

        Arguments:

          - relations : list

             list of object property IDs, e.g. subClassOf, BFO:0000050. If empty, uses all.

          - prefix : String

             if specified, create a subgraph using only classes with this prefix, e.g. ENVO, PATO, GO

        """
        # default method - wrap get_graph
        srcg = self.get_graph()
        if prefix is not None:
            srcg = srcg.subgraph([n for n in srcg.nodes() if n.startswith(prefix+":")])
        if relations is None:
            logging.info("No filtering on "+str(self))
            return srcg
        logging.info("Filtering {} for {}".format(self, relations))
        g = nx.MultiDiGraph()
    
        logging.info("copying nodes")
        for n,d in srcg.nodes_iter(data=True):
            g.add_node(n, attr_dict=d)

        logging.info("copying edges")
        num_edges = 0
        for x,y,d in srcg.edges_iter(data=True):
            if d['pred'] in relations:
                num_edges += 1
                g.add_edge(x,y,attr_dict=d)
        logging.info("Filtered edges: {}".format(num_edges))
        return g

    def merge(self, ontologies):
        """
        TODO: incomplete
        """
        for ont in ontologies:
            g = self.get_graph()
            xg = ont.get_graph()
            for n in xg.nodes():
                g.add_node(n)
            for (o,s,m) in xg.edges(data=True):
                g.add_edge(o,s,attr_dict=m)
            
        
    def subgraph(self, nodes=[]):
        """
        Returns an induced subgraph

        By default this wraps networkx subgraph,
        but this may be overridden in specific implementations
        """
        return self.get_graph().subgraph(nodes)
                
    def extract_subset(self, subset):
        """
        Find all nodes in a subset.
    
        We assume the oboInOwl encoding of subsets, and subset IDs are IRIs
        """
        pass

    def nodes(self):
        """
        Returns all nodes in ontology

        Wraps networkx by default
        """
        return self.get_graph().nodes()

    def node(self, id):
        """
        Returns a node with a given ID

        Wraps networkx by default
        """
        return self.get_graph().node[id]

    def neighbors(self, node, relations=None):
        return self.parents(node, relations=relations) + self.children(node, relations=relations)
        
    def parents(self, node, relations=None):
        """
        Returns all direct parents of specified node.

        Wraps networkx by default.

        Arguments
        ---------

        node: string

           identifier for node in ontology

        relations: list of strings

           list of relation (object property) IDs used to filter

        """
        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        if node in g:
            return g.predecessors(node)
        else:
            return []
    
    def children(self, node, relations=None):
        """
        Returns all direct children of specified node.

        Wraps networkx by default.

        Arguments
        ---------

        node: string

           identifier for node in ontology

        relations: list of strings

           list of relation (object property) IDs used to filter

        """
        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        if node in g:
            return g.successors(node)
        else:
            return []
    
    def ancestors(self, node, relations=None):
        """
        Returns all ancestors of specified node.

        Wraps networkx by default.

        Arguments
        ---------

        node: string

           identifier for node in ontology

        relations: list of strings

           list of relation (object property) IDs used to filter

        """
        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        if node in g:
            return nx.ancestors(g, node)
        else:
            return []

    def descendants(self, node, relations=None):
        """
        Returns all ancestors of specified node.

        Wraps networkx by default.

        Arguments as for ancestors
        """
        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        if node in g:
            return nx.descendants(g, node)
        else:
            return []

    def traverse_nodes(self, qids, up=True, down=False, **args):
        """
        Traverse (optionally) up and (optionally) down from an input set of nodes

        Arguments:

          - qids : list
          - up : boolean
          - down : boolean
          - relations : list
          - prefix : string
        """
        g = self.get_filtered_graph(**args)
        nodes = set()
        for id in qids:
            # reflexive - always add self
            nodes.add(id)
            if down:
                nodes.update(nx.descendants(g, id))
            if up:
                nodes.update(nx.ancestors(g, id))
        return nodes
                


    def get_roots(self, relations=None, prefix=None):
        """
        Get all nodes at root
        """
        g = self.get_filtered_graph(relations=relations, prefix=prefix)
        # note: we also eliminate any singletons, which includes obsolete classes
        roots = [n for n in g.nodes() if len(g.predecessors(n)) == 0 and len(g.successors(n)) > 0]
        return roots
        
    def get_level(self, level, relations=None, **args):
        """
        Get all nodes at a particular level
        """
        g = self.get_filtered_graph(relations)
        nodes = self.get_roots(relations=relations, **args)
        for i in range(level):
            logging.info(" ITERATING TO LEVEL: {} NODES: {}".format(i, nodes))
            nodes = [c for n in nodes
                     for c in g.successors(n)]
        logging.info(" FINAL: {}".format(nodes))
        return nodes

    def parent_index(self, relations=None):
        """
        Returns a list of lists [[CLASS_1, PARENT_1,1, ..., PARENT_1,N], [CLASS_2, PARENT_2,1, PARENT_2,2, ... ] ... ]
        """
        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        l = []
        for n in g:
            l.append([n] ++ g.predecessors(b))
        return l
        
    def logical_definitions(self, nid):
        """
        Retrieves logical definitions for a class id

        Returns: LogicalDefinition
        """
        ldefs = self.all_logical_definitions
        if ldefs is not None:
            #print("TESTING: {} AGAINST LD: {}".format(nid, str(ldefs)))
            return [x for x in ldefs if x.class_id == nid]
        else:
            return []

    def synonyms(self, nid, include_label=False):
        """
        Retrieves synonym objects for a class
        """
        n = self.node(nid)
        syns = []
        if 'meta' in n:
            meta = n['meta']
            if 'synonyms' in meta:
                for obj in meta['synonyms']:
                    syns.append(Synonym(nid, **obj))
        if include_label:
            syns.append(Synonym(nid, val=self.label(nid), pred='label'))
        return syns

    def all_synonyms(self, include_label=False):
        """
        Retrieves all synonyms
        """
        syns = []
        for n in self.nodes():
            syns = syns + self.synonyms(n)
        return syns
    
    def label(self, nid, id_if_null=False):
        """
        Fetches label for a node
        """
        g = self.get_graph()
        if nid in g:
            n = g.node[nid]
            if 'label' in n:
                return n['label']
            else:
                if id_if_null:
                    return nid
                else:
                    return None
        else:
            if id_if_null:
                return nid
            else:
                return None

    def xrefs(self, nid, bidirectional=False):
        """
        Fetches xrefs for a node
        """
        if self.xref_graph is not None:
            xg = self.xref_graph
            if nid not in xg:
                return []
            if bidirectional:
                return xg.neighbors(nid)
            else:
                return [x for x in xg.neighbors(nid) if xg[nid][x]['source'] == nid]
                
        return []

    
    def resolve_names(self, names, **args):
        """
        returns a list of identifiers based on an input list of labels and identifiers.

        Arguments
        ---------

        is_regex : boolean

           if true, treats each name as a regular expression

        is_partial_match : boolean

           if true, treats each name as a regular expression .*name.*

        """
        g = self.get_graph()
        r_ids = []
        for n in names:
            if len(n.split(":")) ==2:
                r_ids.append(n)
            else:
                matches = [nid for nid in g.nodes() if self.is_match(g.node[nid], n, **args)]
                r_ids += matches
        return r_ids

    def is_match(self, node, term, is_partial_match=False, is_regex=False, **args):
        label = node.get('label')
        if term == '%':
            # always match if client passes '%'
            return True
        if label is None:
            label = ''
        if term.find('%') > -1:
            term = term.replace('%','.*')
            is_regex = True
        if is_regex:
            return re.search(term, label) is not None
        if is_partial_match:
            return label.find(term) > -1
        else:
            return label == term
    
    def search(self, searchterm, **args):
        """
        Simple search. Returns list of IDs.

        Arguments: as for resolve_names
        """
        return self.resolve_names([searchterm], **args)

class LogicalDefinition():
    """
    A simple OWL logical definition conforming to the pattern:

        class_id = (genus_id_1 AND ... genus_id_n) AND (P_1 some FILLER_1) AND ... (P_m some FILLER_m)

    """
    def __init__(self, class_id, genus_ids, restrictions):
        """
        Arguments:

         - class_id : string

             the class that is being defined

         - genus_ids : list

             a list of named classes (typically length 1)

         - restrictions : list

             a list of (PROPERTY_ID, FILLER_CLASS_ID) tuples

        """
        self.class_id = class_id
        self.genus_ids = genus_ids
        self.restrictions = restrictions
        
    def __str__(self):
        return "{} =def {} AND {}".format(self.class_id, self.genus_ids, self.restrictions)
    def __repr__(self):
        return self.__str__()

class Synonym():
    """
    Represents a synonym using the OBO model
    """
    
    def __init__(self, class_id, val=None, pred=None, lextype=None, xrefs=None, ontology=None):
        """
        Arguments:

         - class_id : string

             the class that is being defined

         - value : string

             the synonym itself

         - pred: string

             oboInOwl predicate used to model scope. One of: has{Exact,Narrow,Related,Broad}Synonym - may also be 'label'

         - lextype: string

             From an open ended set of types

         - xrefs: list

             Provenance or cross-references to same usage

        """
        pred = pred.replace("http://www.geneontology.org/formats/oboInOwl#","")
        self.class_id = class_id
        self.val = val
        self.pred = pred
        self.lextype = lextype
        self.xrefs = xrefs
        self.ontology = ontology
        
    def __str__(self):
        return '{} "{}" {} {} {}'.format(self.class_id, self.val, self.pred, self.lextype, self.xrefs)
    def __repr__(self):
        return self.__str__()
    
    def __cmp__(self, other):
        (x,y) = (str(self),str(other))
        if x > y:
            return 1
        if x < y:
            return -1
        return 0
