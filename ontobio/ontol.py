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

        **Note**: do not call this directly, use OntologyFactory instead
        """
        self.handle = handle

        # networkx object
        self.graph = graph
        self.xref_graph = xref_graph

        # obograph
        self.graphdoc = graphdoc

        self.all_logical_definitions = []
        
        # alternatively accept a payload object
        if payload is not None:
            self.graph = payload.get('graph')
            self.xref_graph = payload.get('xref_graph')
            self.graphdoc = payload.get('graphdoc')
            self.all_logical_definitions = payload.get('logical_definitions')
        

    def get_graph(self):
        """
        Return a networkx graph for the whole ontology.

        Note: Only implemented for *eager* implementations 

        Return
        ------
        nx.MultiDiGraph
            A networkx MultiDiGraph object representing the complete ontology
        """
        return self.graph

    # consider caching
    def get_filtered_graph(self, relations=None, prefix=None):
        """
        Returns a networkx graph for the whole ontology, for a subset of relations

        Only implemented for eager methods.

        Implementation notes: currently this is not cached

        Arguments
        ---------
          - relations : list
             list of object property IDs, e.g. subClassOf, BFO:0000050. If empty, uses all.
          - prefix : String
             if specified, create a subgraph using only classes with this prefix, e.g. ENVO, PATO, GO
        Return
        ------
        nx.MultiDiGraph
            A networkx MultiDiGraph object representing the filtered ontology
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
        Return an induced subgraph

        By default this wraps networkx subgraph,
        but this may be overridden in specific implementations
        """
        return self.get_graph().subgraph(nodes)

    def subontology(self, nodes=None, minimal=False, relations=None):
        """
        Return a new ontology that is an extract of this one

        Arguments:

        - Nodes: list

            list of node IDs to include in subontology. If None, all are used

        - Relations: list

            list of relation IDs to include in subontology. If None, all are used

        """
        g = None
        if nodes is not None:
            g = self.subgraph(nodes)
        else:
            g = self.get_graph()            
        if minimal:
            from ontobio.slimmer import get_minimal_subgraph
            g = get_minimal_subgraph(g, nodes)
            
        ont = Ontology(graph=g) # TODO - add metadata
        if relations is not None:
            g = ont.get_filtered_graph(relations)
            ont = Ontology(graph=g)
        return ont

    def create_slim_mapping(self, subset=None, subset_nodes=None, relations=None, disable_checks=False):
        """
        Create a dictionary that maps between all nodes in an ontology to a subset

        Arguments
        ---------
        ont : `Ontology`
            Complete ontology to be mapped. Assumed pre-filtered for relationship types
        subset : str
            Name of subset to map to, e.g. goslim_generic
        nodes : list
            If no named subset provided, subset is passed in as list of node ids
        relations : list
            List of relations to filter on
        disable_checks: bool
            Unless this is set, this will prevent a mapping being generated with non-standard relations.
            The motivation here is that the ontology graph may include relations that it is inappropriate to
            propagate gene products over, e.g. transports, has-part
    
        Return
        ------
        dict
            maps all nodes in ont to one or more non-redundant nodes in subset

        Raises
        ------
        ValueError
            if the subset is empty
        """
        if subset is not None:
            subset_nodes = self.extract_subset(subset)
            logging.info("Extracting subset: {} -> {}".format(subset, subset_nodes))
        
        if subset_nodes is None or len(subset_nodes) == 0:
            raise ValueError("subset nodes is blank")
        subset_nodes = set(subset_nodes)
        logging.debug("SUBSET: {}".format(subset_nodes))

        # Use a sub-ontology for mapping
        subont = self
        if relations is not None:
            subont = self.subontology(relations=relations)
            
        if not disable_checks:
            for r in subont.relations_used():
                if r != 'subClassOf' and r != 'BFO:0000050' and r != 'subPropertyOf':
                    raise ValueError("Not safe to propagate over a graph with edge type: {}".format(r))
        
        m = {}
        for n in subont.nodes():
            ancs = subont.ancestors(n, reflexive=True)
            #logging.info("  M: {} -> {}".format(n, ancs))
            ancs_in_subset = subset_nodes.intersection(ancs)
            m[n] = list(ancs_in_subset)
        return m

    def filter_redundant(self, ids):
        """
        Return all non-redundant ids from a list
        """
        sids = set(ids)
        for id in ids:
            sids = sids.difference(self.ancestors(id, reflexive=False))
        return sids
    
    def extract_subset(self, subset, contract=True):
        """
        Return all nodes in a subset.
    
        We assume the oboInOwl encoding of subsets, and subset IDs are IRIs, or IR fragments
        """
        return [n for n in self.nodes() if subset in self.subsets(n, contract=contract)]

    def subsets(self, nid, contract=True):
        """
        Retrieves subset ids for a class or ontology object
        """
        n = self.node(nid)
        subsets = []
        meta = self._meta(nid)
        if 'subsets' in meta:
            subsets = meta['subsets']
        else:
            subsets = []
        if contract:
            subsets = [self._contract_subset(s) for s in subsets]
        return subsets

    def _contract_subset(self, s):
        if s.find("#") > -1:
            return s.split('#')[-1]
        else:
            return s
        
    def _meta(self, nid):
        n = self.node(nid)
        if 'meta' in n:
            return n['meta']
        else:
            return {}
        
    
    def prefixes(self):
        """
        list all prefixes used
        """
        pset = set()
        for n in self.nodes():
            pfx = self.prefix(n)
            if pfx is not None:
                pset.add(pfx)
        return list(pset)

    def prefix(self, nid):
        """
        Return prefix for a node
        """
        parts = nid.split(":")
        if len(parts) > 1:
            return parts[0]
        else:
            return None
    
    def nodes(self):
        """
        Return all nodes in ontology

        Wraps networkx by default
        """
        return self.get_graph().nodes()

    def node(self, id):
        """
        Return a node with a given ID

        Wraps networkx by default
        """
        return self.get_graph().node[id]

    def has_node(self, id):
        """
        True if id identifies a node in the ontology graph
        """
        return id in self.get_graph().node
    
    def sorted_nodes(self):
        """
        Returns all nodes in ontology, after topological sort

        """
        return nx.topological_sort(self.get_graph())
      
    def relations_used(self):
        """
        Return list of all relations used to connect edges
        """
        g = self.get_graph()
        types = set()
        for x,y,d in g.edges_iter(data=True):
            types.add(d['pred'])
        return list(types)
    
    def neighbors(self, node, relations=None):
        return self.parents(node, relations=relations) + self.children(node, relations=relations)
        
    def parents(self, node, relations=None):
        """
        Return all direct parents of specified node.

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
            # TODO: make this more efficient
            g = self.get_filtered_graph(relations)
        if node in g:
            return g.predecessors(node)
        else:
            return []
    
    def children(self, node, relations=None):
        """
        Return all direct children of specified node.

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
    
    def ancestors(self, node, relations=None, reflexive=False):
        """Return all ancestors of specified node.

        The default implementation is to use networkx, but some
        implementations of the Ontology class may use a database or
        service backed implementation, for large graphs.

        Arguments
        ---------
        node : str
            identifier for node in ontology
        reflexive : bool
            if true, return query node in graph
        relations : list
             relation (object property) IDs used to filter

        Returns
        -------
        list[str]
            ancestor node IDs

        """
        if reflexive:
            ancs = self.ancestors(node, relations, reflexive=False)
            ancs.add(node)
            return ancs
            
        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        if node in g:
            return nx.ancestors(g, node)
        else:
            return []

    def descendants(self, node, relations=None, reflexive=False):
        """
        Returns all ancestors of specified node.

        The default implementation is to use networkx, but some
        implementations of the Ontology class may use a database or
        service backed implementation, for large graphs.


        Arguments
        ---------
        node : str
            identifier for node in ontology
        reflexive : bool
            if true, return query node in graph
        relations : list
             relation (object property) IDs used to filter

        Returns
        -------
        list[str]
            descendant node IDs
        """
        if reflexive:
            ancs = self.ancestors(node, relations, reflexive=False)
            return ancs + [node]
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

        Arguments
        ---------
        qids : list[str]
            list of seed node IDs to start from
        up : bool
            if True, include ancestors
        down : bool
            if True, include descendants
        relations : list[str]
            list of relations used to filter

        Return
        ------
        list[str]
            nodes reachable from qids
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
        Get all nodes that lack parents

        Arguments
        ---------
        relations : list[str]
            list of relations used to filter
        prefix : str
            E.g. GO. Exclude nodes that lack this prefix when testing parentage
        """
        g = self.get_filtered_graph(relations=relations, prefix=prefix)
        # note: we also eliminate any singletons, which includes obsolete classes
        roots = [n for n in g.nodes() if len(g.predecessors(n)) == 0 and len(g.successors(n)) > 0]
        return roots
        
    def get_level(self, level, relations=None, **args):
        """
        Get all nodes at a particular level

        Arguments
        ---------
        relations : list[str]
            list of relations used to filter
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
        Returns a mapping of nodes to all direct parents

        Arguments
        ---------
        relations : list[str]
            list of relations used to filter

        Returns:
        list
            list of lists [[CLASS_1, PARENT_1,1, ..., PARENT_1,N], [CLASS_2, PARENT_2,1, PARENT_2,2, ... ] ... ]
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

        Arguments
        ---------
        nid : str
            Node identifier for entity to be queried

        Returns
        -------
        LogicalDefinition
        """
        ldefs = self.all_logical_definitions
        if ldefs is not None:
            #print("TESTING: {} AGAINST LD: {}".format(nid, str(ldefs)))
            return [x for x in ldefs if x.class_id == nid]
        else:
            return []

    def get_node_type(self, nid):
        n = self.node(nid)
        if 'type' in n:
            return n['type']
        return None
        
    def _get_meta_prop(self, nid, prop):
        n = self.node(nid)
        if 'meta' in n:
            meta = n['meta']
            if prop in meta:
                return meta[prop]
        return None

    def _get_meta(self, nid):
        n = self.node(nid)
        if 'meta' in n:
            return n['meta']
        return None

    def _get_basic_property_values(self, nid):
        return self._get_meta_prop(nid, 'basicPropertyValues')
    
    def _get_basic_property_value(self, nid, prop):
        bpvs = self._get_basic_property_values()
        return [x['val'] for x in bpvs in x['pred'] == prop]
    
    def is_obsolete(self, nid):
        """
        True if node is obsolete

        Arguments
        ---------
        nid : str
            Node identifier for entity to be queried
        """
        dep = self._get_meta_prop(nid, 'deprecated')
        return  dep is not None and dep

    def replaced_by(self, nid, strict=True):
        """
        Returns value of 'replaced by' (IAO_0100001) property for obsolete nodes

        Arguments
        ---------
        nid : str
            Node identifier for entity to be queried
        strict: bool
            If true, raise error if cardinality>1. If false, return list if cardinality>1

        Return
        ------
        None if no value set, otherwise returns node id (or list if multiple values, see strict setting)
        """
        vs = self._get_basic_property_value(nid, 'IAO:0100001')
        if len(vs) == 0:
            return None
        elif len(vs) == 1:
            return vs[0]
        else:
            msg = "replaced_by has multiple values: {}".format(vs)
            if strict:
                raise ValueError(msg)
            else:
                logging.error(msg)
                return vs
    
    def synonyms(self, nid, include_label=False):
        """
        Retrieves synonym objects for a class

        Arguments
        ---------
        nid : str
            Node identifier for entity to be queried
        include_label : bool
            If True, include label/names as Synonym objects

        Returns
        -------
        list[Synonym]
            :class:`Synonym` objects
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
    
    def add_synonym(self, syn):
        """
        Adds a synonym for a node
        """
        n = self.node(syn.class_id)
        if 'meta' not in n:
            n['meta'] = {}
        meta = n['meta']
        if 'synonyms' not in meta:
            meta['synonyms'] = []
        meta['synonyms'].append({'val': syn.val,'pred': syn.pred})

    def all_synonyms(self, include_label=False):
        """
        Retrieves all synonyms

        Arguments
        ---------
        include_label : bool
            If True, include label/names as Synonym objects

        Returns
        -------
        list[Synonym]
            :class:`Synonym` objects
        """
        syns = []
        for n in self.nodes():
            syns = syns + self.synonyms(n)
        return syns
    
    def label(self, nid, id_if_null=False):
        """
        Fetches label for a node

        Arguments
        ---------
        nid : str
            Node identifier for entity to be queried
        id_if_null : bool
            If True and node has no label return id as label

        Return
        ------
        str
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

        Arguments
        ---------
        nid : str
            Node identifier for entity to be queried
        bidirection : bool
            If True, include nodes xreffed to nid

        Return
        ------
        list[str]
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

    
    def resolve_names(self, names, synonyms=False, **args):
        """
        returns a list of identifiers based on an input list of labels and identifiers.

        Arguments
        ---------
        names: list
           search terms. '%' treated as wildcard
        synonyms: bool
           if true, search on synonyms in addition to labels
        is_regex : bool
           if true, treats each name as a regular expression
        is_partial_match : bool
           if true, treats each name as a regular expression .*name.*
        """
        g = self.get_graph()
        r_ids = []
        for n in names:
            if len(n.split(":")) ==2:
                r_ids.append(n)
            else:
                matches = set([nid for nid in g.nodes() if self._is_match(self.label(nid), n, **args)])
                if synonyms:
                    for nid in g.nodes():
                        for s in self.synonyms(nid):
                            if self._is_match(s.val, n, **args):
                                matches.add(nid) 
                r_ids += list(matches)
        return r_ids

    def _is_match(self, label, term, is_partial_match=False, is_regex=False, **args):
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

        Arguments
        ---------
        searchterm: list
           search term. '%' treated as wildcard
        synonyms: bool
           if true, search on synonyms in addition to labels
        is_regex : bool
           if true, treats each name as a regular expression
        is_partial_match : bool
           if true, treats each name as a regular expression .*name.*

        Return
        ------
        list
           match node IDs
        """
        return self.resolve_names([searchterm], **args)

class LogicalDefinition():
    """
    A simple OWL logical definition conforming to the pattern:

    ::

        class_id = (genus_id_1 AND ... genus_id_n) AND (P_1 some FILLER_1) AND ... (P_m some FILLER_m)

    See `obographs <https://github.com/geneontology/obographs>`_ docs for more details

    """
    def __init__(self, class_id, genus_ids, restrictions):
        """
        Arguments
        ---------
        class_id : string
            the class that is being defined
        genus_ids : list
            a list of named classes (typically length 1)
        restrictions : list
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

    predmap = dict(
        hasExactSynonym='exact',
        hasBroadSynonym='broad',
        hasNarrowSynonym='narrow',
        hasRelatedSynonym='related')

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

    def scope(self):
        return self.predmap[self.pred].upper()
    
    def __cmp__(self, other):
        (x,y) = (str(self),str(other))
        if x > y:
            return 1
        if x < y:
            return -1
        return 0
