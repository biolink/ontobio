"""Lexical mapping of ontology classes

The core data structure used here is a Mapping Graph. This is a
networkx Graph object (i.e. singly labeled, non-directional) that
connects lexically mapped nodes between two ontologies.

Edge Properties
---------------

idpair: (string,string)
    the pair of identifiers mapped
score: number
    Number between 0 and 100 indicating strength of match based on multiple criteria
synonyms: (Synonym,Synonym)
    pair of Synonym objects (including primary labels) used to create mapping
simscores: (number, number)
    Semantic similarity A to B and B to A respectively.
    Note that false positives or negatives in the ancestors or descendants in the xref graph will lead to bias in these scores.
reciprocal_score: int
    A number between 0 and 4 that indicates whether this was a reciprocal best match (RBM), with additional gradation based on whether
    ties are included. We distinguish between a true BM and a tied BM. 4 indicates true RBM. 1 indicates reciprocal tied BM (ie both are tied BMs). 2 indicates a combo of
    a true BM and a tied BM.
    Note that ties are less likely if semantic similarity is considered in the match.

"""
import networkx as nx
from networkx.algorithms import strongly_connected_components
import logging
import re
from ontobio.ontol import Synonym, Ontology
from collections import defaultdict
import pandas as pd

from marshmallow import Schema, fields, pprint, post_load

LABEL_OR_EXACT = 'label_or_exact'

def default_wsmap():
    """
    Default word to normalized synonym list
    """
    return {
        'a':'',
        'of':'',
        'the':'',
        'i':'1',
        'ii':'2',
        'iii':'3',
        'iv':'4',
        'v':'5',
        'vi':'6',
        'vii':'7',
        'viii':'8',
        'ix':'9',
        'x':'10',
        'xi':'11',
        'xii':'12',
        'xiii':'13',
        'xiv':'14',
        'xv':'15',
        'xvi':'16',
        'xvii':'17',
        'xviii':'18',
        'xix':'19',
        'xx':'20',
        '':''
    }

class LexicalMapEngine():
    """
    generates lexical matches between pairs of ontology classes
    """

    SCORE='score'
    LEXSCORE='lexscore'
    SIMSCORES='simscores'
    CONDITIONAL_PR='cpr'
    
    def __init__(self, wsmap=default_wsmap(), config={}):
        """
        Arguments
        ---------
        wdmap: dict
            maps words to normalized synonyms.
        config: dict
            A configuration conforming to LexicalMapConfigSchema
        """
        # maps label or syn value to Synonym object
        self.lmap = {}
        # maps node id to synonym objects
        self.smap = {}
        self.wsmap = wsmap
        self.npattern = re.compile('[\W_]+')
        self.exclude_obsolete = True
        self.ontology_pairs = None
        self.id_to_ontology_map = defaultdict(list)
        self.merged_ontology = Ontology()
        self.config = config
        self.stats = {}

    def index_ontologies(self, onts):
        logging.info('Indexing: {}'.format(onts))
        for ont in onts:
            self.index_ontology(ont)
        
    def index_ontology(self, ont):
        """
        Adds an ontology to the index

        This iterates through all labels and synonyms in the ontology, creating an index
        """
        self.merged_ontology.merge([ont])
        syns = ont.all_synonyms(include_label=True)
        
        include_id = self._is_meaningful_ids()
        logging.info("Include IDs as synonyms: {}".format(include_id))
        if include_id:
            for n in ont.nodes():
                v = n
                # Get fragment
                if v.startswith('http'):
                    v = re.sub('.*/','',v)
                    v = re.sub('.*#','',v)
                syns.append(Synonym(n, val=v, pred='id'))
        
        logging.info("Indexing {} syns in {}".format(len(syns),ont))
        logging.info("Distinct lexical values: {}".format(len(self.lmap.keys())))
        for syn in syns:
            self.index_synonym(syn, ont)
        for nid in ont.nodes():
            self.id_to_ontology_map[nid].append(ont)

    def label(self, nid):
        return self.merged_ontology.label(nid)
    
    def index_synonym(self, syn, ont):
        """
        Index a synonym

        Typically not called from outside this object; called by `index_ontology`
        """
        if not syn.val:
            if syn.pred == 'label':
                if not self._is_meaningful_ids():
                    logging.error('Use meaningful ids if label not present: {}'.format(syn))
            else:
                logging.warning("Incomplete syn: {}".format(syn))
            return
        if self.exclude_obsolete and ont.is_obsolete(syn.class_id):
            return

        syn.ontology = ont
        prefix,_ = ont.prefix_fragment(syn.class_id)
        
        v = syn.val

        # chebi 'synonyms' are often not real synonyms
        # https://github.com/ebi-chebi/ChEBI/issues/3294
        if not re.match('[a-zA-Z]',v):
            if prefix != 'CHEBI':
                logging.warning('Ignoring suspicous synonym: {}'.format(syn))
            return
        
        # Add spaces separating camelcased strings
        v = re.sub('([a-z])([A-Z])',r'\1 \2',v)
        
        # always use lowercase when comparing
        # we may want to make this configurable in future
        v = v.lower()
        
        nv = self._normalize(v, self.wsmap)
        
        self._index_synonym_val(syn, v)
        nweight = self._get_config_val(prefix, 'normalized_form_confidence', 0.85)
        if nweight > 0:
            if nv != v:
                nsyn = Synonym(syn.class_id,
                               val=syn.val,
                               pred=syn.pred,
                               lextype=syn.lextype,
                               ontology=ont,
                               confidence=syn.confidence * nweight)
                self._index_synonym_val(nsyn, nv)
        
                
    def _index_synonym_val(self, syn, v):
        lmap = self.lmap
        smap = self.smap
        cid = syn.class_id
        if v not in lmap:
            lmap[v] = []
        lmap[v].append(syn)
        if cid not in smap:
            smap[cid] = []
        smap[cid].append(syn)
        

    def _normalize(self, s, wsmap):
        toks = []
        for tok in list(set(self.npattern.sub(' ', s).split(' '))):
            if tok in wsmap:
                tok=wsmap[tok]
            if tok != "":
                toks.append(tok)
        toks.sort()
        return " ".join(toks)

    def _get_config_val(self, prefix, k, default=None):
        v = None
        for oc in self.config.get('ontology_configurations', []):
            if prefix == oc.get('prefix', ''):
                v = oc.get(k, None)
        if v is None:
            v = self.config.get(k, None)
        if v is None:
            v = default
        return v
    
    def _is_meaningful_ids(self):
        return self.config.get('meaningful_ids', False)
    
    def find_equiv_sets(self):
        return self.lmap

    def get_xref_graph(self):
        """

        Generate mappings based on lexical properties and return as nx graph.

        Algorithm
        ~~~~~~~~~

        - A dictionary is stored between ref:`Synonym` values and synonyms. See ref:`index_synonym`.
          Note that Synonyms include the primary label

        - Each key in the dictionary is examined to determine if there exist two Synonyms from
          different ontology classes

        This avoids N^2 pairwise comparisons: instead the time taken is linear

        After initial mapping is made, additional scoring is performed on each mapping

        Edge properties
        ~~~~~~~~~~~~~~~
        The return object is a nx graph, connecting pairs of ontology classes.

        Edges are annotated with metadata about how the match was found:

        syns: pair
            pair of `Synonym` objects, corresponding to the synonyms for the two nodes
        score: int
            score indicating strength of mapping, between 0 and 100

        Returns
        -------
        Graph
            nx graph (bidirectional)
        """

        # initial graph; all matches
        g = nx.MultiDiGraph()

        # lmap collects all syns by token
        items = self.lmap.items()
        logging.info("collecting initial xref graph, items={}".format(len(items)))
        i = 0
        sum_nsyns = 0
        n_skipped = 0
        has_self_comparison = False
        if self.ontology_pairs:
            for (o1id,o2id) in self.ontology_pairs:
                if o1id == o2id:
                    has_self_comparison = True

        for (v,syns) in items:
            sum_nsyns += len(syns)
            i += 1
            if i % 1000 == 1:
                logging.info('{}/{}  lexical items avgSyns={}, skipped={}'.format(i,len(items), sum_nsyns/len(items), n_skipped))
            if len(syns) < 2:
                n_skipped += 1
                next
            if len(syns) > 10:
                logging.info('Syns for {} = {}'.format(v,len(syns)))
            for s1 in syns:
                s1oid = s1.ontology.id
                s1cid = s1.class_id
                for s2 in syns:
                    # optimization step: although this is redundant with _is_comparable,
                    # we avoid inefficient additional calls
                    if s1oid == s2.ontology.id and not has_self_comparison:
                        next
                    if s1cid != s2.class_id:
                        if self._is_comparable(s1,s2):
                            g.add_edge(s1.class_id, s2.class_id, syns=(s1,s2))

        logging.info("getting best supporting synonym pair for each match")
        # graph of best matches
        xg = nx.Graph()
        for i in g.nodes():
            for j in nx.neighbors(g,i):
                best = 0
                bestm = None
                for m in g[i][j].values():
                    (s1,s2) = m['syns']
                    score = self._combine_syns(s1,s2)
                    if score > best:
                        best = score
                        bestm = m
                syns = bestm['syns']
                xg.add_edge(i, j,
                            score=best,
                            lexscore=best,
                            syns=syns,
                            idpair=(i,j))

        self.score_xrefs_by_semsim(xg)
        self.assign_best_matches(xg)
        logging.info("finished xref graph")
        return xg

    # true if syns s1 and s2 should be compared.
    #  - if ontology_pairs is set, then only consider (s1,s2) if their respective source ontologies are in the list of pairs
    #  - otherwise compare all classes, but only in one direction
    def _is_comparable(self, s1, s2):
        if s1.class_id == s2.class_id:
            return False
        if self.ontology_pairs is not None:
            #logging.debug('TEST: {}{} in {}'.format(s1.ontology.id, s2.ontology.id, self.ontology_pairs))
            return (s1.ontology.id, s2.ontology.id) in self.ontology_pairs
        else:
            return s1.class_id < s2.class_id

    def _blanket(self, nid):
        nodes = set()
        for ont in self.id_to_ontology_map[nid]:
            nodes.update(ont.ancestors(nid))
            nodes.update(ont.descendants(nid))
        return list(nodes)
    
    def score_xrefs_by_semsim(self, xg, ont=None):
        """
        Given an xref graph (see ref:`get_xref_graph`), this will adjust scores based on
        the semantic similarity of matches.
        """
        logging.info("scoring xrefs by semantic similarity for {} nodes in {}".format(len(xg.nodes()), ont))
        for (i,j,d) in xg.edges_iter(data=True):
            #ancs1 = ont.ancestors(i) + ont.descendants(i)
            #ancs2 = ont.ancestors(j) + ont.descendants(j)
            ancs1 = self._blanket(i)
            ancs2 = self._blanket(j)
            s1 = self._sim(xg, ancs1, ancs2)
            s2 = self._sim(xg, ancs2, ancs1)
            s = 1 - ((1-s1) * (1-s2))
            logging.debug("Score {} x {} = {} x {} = {} // {}".format(i,j,s1,s2,s, d))
            xg[i][j][self.SIMSCORES] = (s1,s2)
            xg[i][j][self.SCORE] *= s

    def _sim(self, xg, ancs1, ancs2):
        xancs1 = set()
        for a in ancs1:
            if a in xg:
                # TODO: restrict this to neighbors in single ontology
                xancs1.update(xg.neighbors(a))
        logging.debug('SIM={}/{} ## {}'.format(len(xancs1.intersection(ancs2)), len(xancs1), xancs1.intersection(ancs2), xancs1))
        return (1+len(xancs1.intersection(ancs2))) / (1+len(xancs1))


    def _neighbors_by_ontology(self, xg, nid):
        xrefmap = defaultdict(list)
        for x in xg.neighbors(nid):
            score = xg[nid][x][self.SCORE]
            for ont in self.id_to_ontology_map[x]:
                xrefmap[ont.id].append( (score,x) )
        return xrefmap

    def _dirn(self, edge, i, j):
        if edge['idpair'] == (i,j):
            return 'fwd'
        elif edge['idpair'] == (j,i):
            return 'rev'
        else:
            return None
        
    def assign_best_matches(self, xg):
        """
        For each node in the xref graph, tag best match edges
        """
        logging.info("assigning best matches for {} nodes".format(len(xg.nodes())))
        for i in xg.nodes():
            xrefmap = self._neighbors_by_ontology(xg, i)
            for (ontid,score_node_pairs) in xrefmap.items():
                score_node_pairs.sort()
                (best_score,best_node) = score_node_pairs[0]
                logging.info("BEST for {}: {} in {} from {}".format(i, best_node, ontid, score_node_pairs))
                edge = xg[i][best_node]
                dirn = self._dirn(edge, i, best_node)
                best_kwd = 'best_' + dirn
                if len(score_node_pairs) == 1 or score_node_pairs[0] > score_node_pairs[1]:
                    edge[best_kwd] = 2
                else:
                    edge[best_kwd] = 1
                for (score,j) in score_node_pairs:
                    edge_ij = xg[i][j]
                    dirn_ij = self._dirn(edge_ij, i, j)
                    edge_ij['cpr_'+dirn_ij] = score / sum([s for s,_ in score_node_pairs])
        for (i,j,edge) in xg.edges_iter(data=True):
            # reciprocal score is set if (A) i is best for j, and (B) j is best for i
            rs = 0
            if 'best_fwd' in edge and 'best_rev' in edge:
                rs = edge['best_fwd'] * edge['best_rev']
            edge['reciprocal_score'] = rs
            edge['cpr'] = edge['cpr_fwd'] * edge['cpr_rev']
        
    def grouped_mappings(self,id):
        """
        return all mappings for a node, grouped by ID prefix
        """
        g = self.get_xref_graph()
        m = {}
        for n in g.neighbors(id):
            [prefix, local] = n.split(':')
            if prefix not in m:
                m[prefix] = []
            m[prefix].append(n)
        return m

    def unmapped_nodes(self, xg, rs_threshold=0):
        unmapped_list = []
        for nid in self.merged_ontology.nodes():
            if nid in xg:
                for (j,edge) in xg[nid].items():
                    rs = edge.get('reciprocal_score',0)
                    if rs < rs_threshold:
                        unmapped_list.append(nid)
            else:
                unmapped_list.append(nid)
        return unmapped_list

    # scores a pairwise combination of synonyms. This will be a mix of
    #  * individual confidence in the synonyms themselves
    #  * confidence of equivalence based on scopes
    def _combine_syns(self, s1,s2):
        cpred = self._combine_preds(s1.pred, s2.pred)
        s = self._pred_score(cpred)
        s *= s1.confidence * s2.confidence
        logging.debug("COMBINED: {} + {} = {}/{}".format(s1,s2,cpred,s))
        return s
    
    def _rollup(self, p):
        if p == 'label':
            return LABEL_OR_EXACT
        if p == 'hasExactSynonym':
            return LABEL_OR_EXACT
        return p
    
    def _combine_preds(self, p1, p2):
        if p1 == p2:
            return p1
        if self._rollup(p1) == self._rollup(p2):
            return self._rollup(p1)
        return p1 + p2

    ## TODO: allow this to be weighted by ontology
    def _pred_score(self,p):
        if p == 'label':
            return 100
        if p == LABEL_OR_EXACT:
            return 90
        if p == 'hasExactSynonym':
            return 90
        return 50

    def _in_clique(self, x, cliques):
        for s in cliques:
            if x in s:
                return s
        return set()
    
    def as_dataframe(self, xg):
        cliques = self.cliques(xg)
        ont = self.merged_ontology
        items = []
        for x,y,d in xg.edges_iter(data=True):
            # xg is a non-directional Graph object.
            # to get a deterministic ordering we use the idpair key
            (x,y) = d['idpair']
            (s1,s2)=d['syns']
            (ss1,ss2)=d['simscores']
            clique = self._in_clique(x, cliques)
            #ancs = nx.ancestors(g,x)
            item = {'left':x, 'left_label':ont.label(x),
                    'right':y, 'right_label':ont.label(y),
                    'score':d['score'],
                    'left_match_type': s1.pred,
                    'right_match_type': s2.pred,
                    'left_match_val': s1.val,
                    'right_match_val': s2.val,
                    'left_simscore':ss1,
                    'right_simscore':ss2,
                    'reciprocal_score':d.get('reciprocal_score',0),
                    'conditional_pr_equiv': d.get('cpr'),
                    'equiv_clique_size': len(clique)}
            items.append(item)

        ix = ['left', 'left_label', 'right', 'right_label',
              'left_match_type', 'right_match_type',
              'left_match_val', 'right_match_val', 
              'score', 'left_simscore', 'right_simscore', 'reciprocal_score',
              'conditional_pr_equiv', 'equiv_clique_size']
        df = pd.DataFrame(items, columns=ix)
        return df
    
    def cliques(self, xg):
        """
        Return all equivalence set cliques, assuming each edge in the xref graph is treated as equivalent,
        and all edges in ontology are subClassOf

        Arguments
        ---------
        xg : Graph
            an xref graph

        Returns
        -------
        list of sets
        """
        g = nx.DiGraph()
        for x,y in self.merged_ontology.get_graph().edges():
            g.add_edge(x,y)
        for x,y in xg.edges():
            g.add_edge(x,y)
            g.add_edge(y,x)
        return list(strongly_connected_components(g))
        
            
        

### MARSHMALLOW SCHEMAS
                        
class ScopeConfidenceMapSchema(Schema):
    """
    Maps scope predicates (label, hasExactSynonym etc) to confidences (0<=1.0).

    Typically labels and exact matches have higher confidence, although this
    may vary with ontology
    """
    label = fields.Float(default=1.0, description="confidence of label matches")
    hasExactSynonym = fields.Float(default=0.9, description="confidence of exact matches")
    hasRelatedSynonym = fields.Float(default=0.5, description="confidence of related matches")
    hasBroadSynonym = fields.Float(default=0.5, description="confidence of broad matches")
    hasNarrowSynonym = fields.Float(default=0.5, description="confidence of narrow matches")
    other = fields.Float(default=0.25, description="confidence of other kinds of matches")

class OntologyConfigurationSchema(Schema):
    """
    configuration that is specific to an ontology
    """
    prefix = fields.String(description="prefix of IDs in ontology, e.g. UBERON")
    scope_confidence_map = fields.Nested(ScopeConfidenceMapSchema(), description="local scope-confidence map")
    normalized_form_confidence = fields.Float(default=0.85, description="confidence of a synonym value derived via normalization (e.g. canonical ordering of tokens)")
    
class LexicalMapConfigSchema(Schema):
    """
    global configuration
    """
    scope_confidence_map = fields.Nested(ScopeConfidenceMapSchema(), description="global scope-confidence map. May be overridden by ontologies")
    ontology_configurations = fields.List(fields.Nested(OntologyConfigurationSchema()), description="configurations that are specific to an ontology")
    normalized_form_confidence = fields.Float(default=0.85, description="confidence of a synonym value derived via normalization (e.g. canonical ordering of tokens)")
