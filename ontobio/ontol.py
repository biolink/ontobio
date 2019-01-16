"""
A module for representing simple graph-oriented views of an ontology

See also:

 - ontol_factory.py

"""

import networkx as nx
import logging
import re

logger = logging.getLogger(__name__)

class Ontology():
    """An object that represents a basic graph-oriented view over an ontology.

    The ontology may be represented in memory, or it may be located
    remotely. See subclasses for details.

    The default implementation is an in-memory wrapper onto the python networkx library

    """

    def __init__(self,
                 handle=None,
                 id=None,
                 graph=None,
                 xref_graph=None,
                 meta=None,
                 payload=None,
                 graphdoc=None):
        """
        initializes based on an ontology name.

        **Note**: do not call this directly, use OntologyFactory instead
        """
        self.handle = handle
        self.meta = meta
        if id is None:
            if payload is not None:
                id = payload.get('id')
            if id is None:
                id = handle
        self.id = id

        # networkx object
        self.graph = graph
        if self.graph is None:
            self.graph = nx.MultiDiGraph()
        logger.debug('Graph initialized, nodes={}'.format(self.graph.nodes()))
        self.xref_graph = xref_graph

        # obograph
        self.graphdoc = graphdoc

        self.all_logical_definitions = []

        # alternatively accept a payload object
        if payload is not None:
            self.meta = payload.get('meta')
            self.graph = payload.get('graph')
            self.xref_graph = payload.get('xref_graph')
            self.graphdoc = payload.get('graphdoc')
            self.all_logical_definitions = payload.get('logical_definitions')

    def __str__(self):
        return '{} handle: {} meta: {}'.format(self.id, self.handle, self.meta)
    def __repr__(self):
        return self.__str__()

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

        # trigger synonym cache
        self.all_synonyms()
        self.all_obsoletes()

        # default method - wrap get_graph
        srcg = self.get_graph()
        if prefix is not None:
            srcg = srcg.subgraph([n for n in srcg.nodes() if n.startswith(prefix+":")])
        if relations is None:
            logger.info("No filtering on "+str(self))
            return srcg
        logger.info("Filtering {} for {}".format(self, relations))
        g = nx.MultiDiGraph()

        # TODO: copy full metadata
        logger.info("copying nodes")
        for (n,d) in srcg.nodes(data=True):
            g.add_node(n, **d)

        logger.info("copying edges")
        num_edges = 0
        for (x,y,d) in srcg.edges(data=True):
            if d['pred'] in relations:
                num_edges += 1
                g.add_edge(x,y,**d)
        logger.info("Filtered edges: {}".format(num_edges))
        return g

    def merge(self, ontologies):
        """
        Merges specified ontology into current ontology
        """
        if self.xref_graph is None:
            self.xref_graph = nx.MultiGraph()
        logger.info("Merging source: {} xrefs: {}".format(self, len(self.xref_graph.edges())))
        for ont in ontologies:
            logger.info("Merging {} into {}".format(ont, self))
            g = self.get_graph()
            srcg = ont.get_graph()
            for n in srcg.nodes():
                g.add_node(n, **srcg.node[n])
            for (o,s,m) in srcg.edges(data=True):
                g.add_edge(o,s,**m)
            if ont.xref_graph is not None:
                for (o,s,m) in ont.xref_graph.edges(data=True):
                    self.xref_graph.add_edge(o,s,**m)

    def subgraph(self, nodes=None):
        """
        Return an induced subgraph

        By default this wraps networkx subgraph,
        but this may be overridden in specific implementations
        """
        if nodes is None:
            nodes = []
        return self.get_graph().subgraph(nodes)

    def subontology(self, nodes=None, minimal=False, relations=None):
        """
        Return a new ontology that is an extract of this one

        Arguments
        ---------
        - nodes: list
            list of node IDs to include in subontology. If None, all are used
        - relations: list
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

        ont = Ontology(graph=g, xref_graph=self.xref_graph) # TODO - add metadata
        if relations is not None:
            g = ont.get_filtered_graph(relations)
            ont = Ontology(graph=g, xref_graph=self.xref_graph)
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
            logger.info("Extracting subset: {} -> {}".format(subset, subset_nodes))

        if subset_nodes is None or len(subset_nodes) == 0:
            raise ValueError("subset nodes is blank")
        subset_nodes = set(subset_nodes)
        logger.debug("SUBSET: {}".format(subset_nodes))

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
            ancs_in_subset = subset_nodes.intersection(ancs)
            m[n] = list(subont.filter_redundant(ancs_in_subset))
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

    def prefix_fragment(self, nid):
        """
        Return prefix and fragment/localid for a node
        """
        sep=':'
        if nid.startswith('http'):
            if '#' in nid:
               sep='#'
            else:
                sep='/'
        parts = nid.split(sep)
        frag = parts.pop()
        prefix = sep.join(parts)
        return prefix, frag

    def prefix(self, nid):
        """
        Return prefix for a node
        """
        pfx,_ = self.prefix_fragment(nid)
        return pfx

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

    def node_type(self, id):
        """
        If stated, either CLASS, PROPERTY or INDIVIDUAL
        """
        return self.node(id)['type']

    def relations_used(self):
        """
        Return list of all relations used to connect edges
        """
        g = self.get_graph()
        types = set()
        for (x,y,d) in g.edges(data=True):
            types.add(d['pred'])
        return list(types)

    def neighbors(self, node, relations=None):
        return self.parents(node, relations=relations) + self.children(node, relations=relations)

    def child_parent_relations(self, subj, obj, graph=None):
        """
        Get all relationship type ids between a subject and a parent.

        Typically only one relation ID returned, but in some cases there may be more than one

        Arguments
        ---------
        subj: string
            Child (subject) id
        obj: string
            Parent (object) id

        Returns
        -------
        list
        """
        if graph is None:
            graph = self.get_graph()
        preds = set()
        for _,ea in graph[obj][subj].items():
            preds.add(ea['pred'])
        logger.debug('{}->{} = {}'.format(subj,obj,preds))
        return preds

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
        g = self.get_graph()
        if node in g:
            parents = list(g.predecessors(node))
            if relations is None:
                return parents
            else:
                rset = set(relations)
                return [p for p in parents if len(self.child_parent_relations(node, p, graph=g).intersection(rset)) > 0 ]
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
        g = self.get_graph()
        if node in g:
            children = list(g.successors(node))
            if relations is None:
                return children
            else:
                rset = set(relations)
                return [c for c in children if len(self.child_parent_relations(c, node, graph=g).intersection(rset)) > 0 ]
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
            ancs.append(node)
            return ancs

        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        if node in g:
            return list(nx.ancestors(g, node))
        else:
            return []

    def descendants(self, node, relations=None, reflexive=False):
        """
        Returns all descendants of specified node.

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
            decs = self.descendants(node, relations, reflexive=False)
            decs.append(node)
            return decs
        g = None
        if relations is None:
            g = self.get_graph()
        else:
            g = self.get_filtered_graph(relations)
        if node in g:
            return list(nx.descendants(g, node))
        else:
            return []


    def equiv_graph(self):
        """
        Returns
        -------
        graph
            bidirectional networkx graph of all equivalency relations
        """
        eg = nx.Graph()
        for (u,v,d) in self.get_graph().edges(data=True):
            if d['pred'] == 'equivalentTo':
                eg.add_edge(u,v)
        return eg


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
        roots = [n for n in g.nodes() if len(list(g.predecessors(n))) == 0 and len(list(g.successors(n))) > 0]
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
            logger.info(" ITERATING TO LEVEL: {} NODES: {}".format(i, nodes))
            nodes = [c for n in nodes
                     for c in g.successors(n)]
        logger.info(" FINAL: {}".format(nodes))
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
            l.append([n] + list(g.predecessors(n)))
        return l

    def text_definition(self, nid):
        """
        Retrieves logical definitions for a class or relation id

        Arguments
        ---------
        nid : str
            Node identifier for entity to be queried

        Returns
        -------
        TextDefinition
        """
        tdefs = []
        meta = self._meta(nid)
        if 'definition' in meta:
            obj = meta['definition']
            return TextDefinition(nid, **obj)
        else:
            return None


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
        r =  self._get_meta_prop(nid, 'basicPropertyValues')
        if r is None:
            return []
        else:
            return r

    def _get_basic_property_value(self, nid, prop):
        bpvs = self._get_basic_property_values(nid)
        return [x['val'] for x in bpvs if x['pred'] == prop]

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
        if len(vs) > 1:
            msg = "replaced_by has multiple values: {}".format(vs)
            if strict:
                raise ValueError(msg)
            else:
                logger.error(msg)

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

    def add_node(self, id, label=None, type='CLASS', meta=None):
        """
        Add a new node to the ontology
        """
        g = self.get_graph()
        if meta is None:
            meta={}
        g.add_node(id, label=label, type=type, meta=meta)

    def add_text_definition(self, textdef):
        """
        Add a new text definition to the ontology
        """
        self._add_meta_element(textdef.subject, 'definition', textdef.as_dict())

    def set_obsolete(self, nid):
        if nid not in self.get_graph():
            self.add_node(nid)
        self._add_meta_element(nid, 'deprecated', True)

    def _add_meta_element(self, id, k, edict):
        n = self.node(id)
        if n is None:
            raise ValueError('no such node {}'.format(id))
        if 'meta' not in n:
            n['meta'] = {}
        n['meta'][k] = edict

    def inline_xref_graph(self):
        """
        Copy contents of xref_graph to inlined meta object for each node
        """
        xg = self.xref_graph
        for n in self.nodes():
            if n in xg:
                self._add_meta_element(n, 'xrefs', [{'val':x} for x in xg.neighbors(n)])

    def add_parent(self, id, pid, relation='subClassOf'):
        """
        Add a new edge to the ontology
        """
        g = self.get_graph()
        g.add_edge(pid, id, pred=relation)

    def add_xref(self, id, xref):
        """
        Adds an xref to the xref graph
        """
        # note: does not update meta object
        if self.xref_graph is None:
            self.xref_graph = nx.MultiGraph()
        self.xref_graph.add_edge(xref, id)

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
        meta['synonyms'].append(syn.as_dict())

    def add_to_subset(self, id, s):
        """
        Adds a node to a subset
        """
        n = self.node(id)
        if 'meta' not in n:
            n['meta'] = {}
        meta = n['meta']
        if 'subsets' not in meta:
            meta['subsets'] = []
        meta['subsets'].append(s)

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
            syns = syns + self.synonyms(n, include_label=include_label)
        return syns

    def all_obsoletes(self):
        """
        Returns all obsolete nodes
        """
        return [n for n in self.nodes() if self.is_obsolete(n)]

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
                return list(xg.neighbors(nid))
            else:
                return [x for x in xg.neighbors(nid) if xg[nid][x][0]['source'] == nid]

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
            logger.debug("Searching for {} syns={}".format(n,synonyms))
            if len(n.split(":")) == 2:
                r_ids.append(n)
            else:
                matches = set([nid for nid in g.nodes() if self._is_match(self.label(nid), n, **args)])
                if synonyms:
                    logger.debug("Searching syns for {}".format(names))
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

class AbstractPropertyValue(object):
    """
    Abstract superclass of all property-value mapping classes.
    These correspond to Annotations in OWL
    """
    def __str__(self):
        return '{} "{}" {}'.format(self.subject, self.val, self.xrefs)
    def __repr__(self):
        return self.__str__()

    def __cmp__(self, other):
        (x,y) = (str(self),str(other))
        if x > y:
            return 1
        elif x < y:
            return -1
        else:
            return 0

class TextDefinition(AbstractPropertyValue):
    """
    Represents a textual definition for a class or relation
    """

    def __init__(self, subject, val=None, xrefs=None, ontology=None):
        """
        Arguments
        ---------
         - subject : string
             id for the class or relation that is being defined
         - val : string
             the definition itself
         - xrefs: list
             Provenance or cross-references to same usage
        """
        self.subject = subject
        self.val = val
        self.xrefs = xrefs
        self.ontology = ontology

    def as_dict(self):
        """
        Returns TextDefinition as obograph dict
        """
        return {
            'val': self.val,
            'xrefs': self.xrefs
        }

class Synonym(AbstractPropertyValue):
    """
    Represents a synonym using the OBO model
    """

    predmap = dict(
        label='label',
        hasExactSynonym='exact',
        hasBroadSynonym='broad',
        hasNarrowSynonym='narrow',
        hasRelatedSynonym='related')

    def __init__(self, class_id, val=None, pred='hasRelatedSynonym', lextype=None, xrefs=None, ontology=None, confidence=1.0):
        """
        Arguments
        ---------
         - class_id : string
             the class that is being defined
         - val : string
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
        self.confidence = confidence

    def __str__(self):
        return '{} "{}" {} {} {} {}'.format(self.class_id, self.val, self.pred, self.lextype, self.xrefs, self.confidence)
    def __repr__(self):
        return self.__str__()

    def scope(self):
        if self.pred in self.predmap:
            return self.predmap[self.pred].upper()
        else:
            return self.pred.upper()

    def is_label(self):
        return self.pred == 'label'

    def is_abbreviation(self, v=None):
        if v is not None:
            self.lextype = 'abbreviation'
        return self.lextype is not None and self.lextype.lower() == 'abbreviation'

    def exact_or_label(self):
        return self.pred == 'hasExactSynonym' or self.pred == 'label'

    def as_dict(self):
        """
        Returns Synonym as obograph dict
        """
        # TODO: complete metadata
        return {
            'pred': self.pred,
            'val': self.val,
            'xrefs': self.xrefs
        }

    def __cmp__(self, other):
        (x,y) = (str(self),str(other))
        if x > y:
            return 1
        if x < y:
            return -1
        return 0
