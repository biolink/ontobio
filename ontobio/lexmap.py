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
import numpy as np
import math

from marshmallow import Schema, fields, pprint, post_load

LABEL_OR_EXACT = 'label_or_exact'

def logit(p):
    return math.log2(p/(1-p))
def inv_logit(w):
    return 1/(1+2**(-w))

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
    
    def __init__(self, wsmap=default_wsmap(), config=None):
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
        self.config = config if config is not None else {}
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
                syns.append(Synonym(n, val=v, pred='label'))
        
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
                    if not ont.is_obsolete(syn.class_id):
                        pass
                        #logging.error('Use meaningful ids if label not present: {}'.format(syn))
            else:
                logging.warning("Incomplete syn: {}".format(syn))
            return
        if self.exclude_obsolete and ont.is_obsolete(syn.class_id):
            return

        syn.ontology = ont
        prefix,_ = ont.prefix_fragment(syn.class_id)
        
        v = syn.val

        caps_match = re.match('[A-Z]+',v)
        if caps_match:
            # if > 75% of length is caps, assume abbreviation
            if caps_match.span()[1] >= len(v)/3:
                syn.is_abbreviation(True)
                
        # chebi 'synonyms' are often not real synonyms
        # https://github.com/ebi-chebi/ChEBI/issues/3294
        if not re.match('.*[a-zA-Z]',v):
            if prefix != 'CHEBI':
                logging.warning('Ignoring suspicous synonym: {}'.format(syn))
            return
        
        v = self._standardize_label(v)

        # TODO: do this once ahead of time
        wsmap = {}
        for w,s in self.wsmap.items():
            wsmap[w] = s
        for ss in self._get_config_val(prefix,'synsets',[]):
            # TODO: weights
            wsmap[ss['synonym']] = ss['word']
        nv = self._normalize_label(v, wsmap)
        
        self._index_synonym_val(syn, v)
        nweight = self._get_config_val(prefix, 'normalized_form_confidence', 0.8)
        if nweight > 0 and not syn.is_abbreviation():
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

    def _standardize_label(self, v):
        # Add spaces separating camelcased strings
        v = re.sub('([a-z])([A-Z])',r'\1 \2',v)
        
        # always use lowercase when comparing
        # we may want to make this configurable in future
        v = v.lower()
        return v

    def _normalize_label(self, s, wsmap):
        """
        normalized form of a synonym
        """
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
            for j in g.neighbors(i):
                best = 0
                bestm = None
                for m in g.get_edge_data(i,j).values():
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
        if self.merged_ontology.xref_graph is not None:
            self.compare_to_xrefs(xg, self.merged_ontology.xref_graph)
        else:
            logging.error("No xref graph for merged ontology")
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
        for (i,j,d) in xg.edges(data=True):
            pfx1 = self._id_to_ontology(i)
            pfx2 = self._id_to_ontology(j)
            ancs1 = self._blanket(i)
            ancs2 = self._blanket(j)
            s1,_,_ = self._sim(xg, ancs1, ancs2, pfx1, pfx2)
            s2,_,_ = self._sim(xg, ancs2, ancs1, pfx2, pfx1)
            s = 1 - ((1-s1) * (1-s2))
            logging.debug("Score {} x {} = {} x {} = {} // {}".format(i,j,s1,s2,s, d))
            xg[i][j][self.SIMSCORES] = (s1,s2)
            xg[i][j][self.SCORE] *= s

    def _sim(self, xg, ancs1, ancs2, pfx1, pfx2):
        """
        Compare two lineages
        """
        xancs1 = set()
        for a in ancs1:
            if a in xg:
                # TODO: restrict this to neighbors in single ontology
                for n in xg.neighbors(a):
                    pfx = self._id_to_ontology(n)
                    if pfx == pfx2:
                        xancs1.add(n)
        logging.debug('SIM={}/{} ## {}'.format(len(xancs1.intersection(ancs2)), len(xancs1), xancs1.intersection(ancs2), xancs1))
        n_shared = len(xancs1.intersection(ancs2))
        n_total = len(xancs1)
        return (1+n_shared) / (1+n_total), n_shared, n_total

    # given an ontology class id,
    # return map keyed by ontology id, value is a list of (score, ext_class_id) pairs
    def _neighborscores_by_ontology(self, xg, nid):
        xrefmap = defaultdict(list)
        for x in xg.neighbors(nid):
            score = xg[nid][x][self.SCORE]
            for ont in self.id_to_ontology_map[x]:
                xrefmap[ont.id].append( (score,x) )
        return xrefmap
    
    # normalize direction
    def _dirn(self, edge, i, j):
        if edge['idpair'] == (i,j):
            return 'fwd'
        elif edge['idpair'] == (j,i):
            return 'rev'
        else:
            return None

    def _id_to_ontology(self, id):
        return self.merged_ontology.prefix(id)
        #onts = self.id_to_ontology_map[id]
        #if len(onts) > 1:
        #    logging.warning(">1 ontology for {}".format(id))
        
    def compare_to_xrefs(self, xg1, xg2):
        """
        Compares a base xref graph with another one
        """
        ont = self.merged_ontology
        for (i,j,d) in xg1.edges(data=True):
            ont_left = self._id_to_ontology(i)
            ont_right = self._id_to_ontology(j)
            unique_lr = True
            num_xrefs_left = 0
            same_left = False
            if i in xg2:
                for j2 in xg2.neighbors(i):
                    ont_right2 = self._id_to_ontology(j2)
                    if ont_right2 == ont_right:
                        unique_lr = False
                        num_xrefs_left += 1
                        if j2 == j:
                            same_left = True
            unique_rl = True
            num_xrefs_right = 0
            same_right = False
            if j in xg2:
                for i2 in xg2.neighbors(j):
                    ont_left2 = self._id_to_ontology(i2)
                    if ont_left2 == ont_left:
                        unique_rl = False
                        num_xrefs_right += 1
                        if i2 == i:
                            same_right = True

            (x,y) = d['idpair']
            xg1[x][y]['left_novel'] = num_xrefs_left==0
            xg1[x][y]['right_novel'] = num_xrefs_right==0
            xg1[x][y]['left_consistent'] = same_left
            xg1[x][y]['right_consistent'] = same_right

        
    
    def assign_best_matches(self, xg):
        """
        For each node in the xref graph, tag best match edges
        """
        logging.info("assigning best matches for {} nodes".format(len(xg.nodes())))
        for i in xg.nodes():
            xrefmap = self._neighborscores_by_ontology(xg, i)
            for (ontid,score_node_pairs) in xrefmap.items():
                score_node_pairs.sort(reverse=True)
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
        for (i,j,edge) in xg.edges(data=True):
            # reciprocal score is set if (A) i is best for j, and (B) j is best for i
            rs = 0
            if 'best_fwd' in edge and 'best_rev' in edge:
                rs = edge['best_fwd'] * edge['best_rev']
            edge['reciprocal_score'] = rs
            edge['cpr'] = edge['cpr_fwd'] * edge['cpr_rev']

    def _best_match_syn(self, sx, sys, scope_map):
        """
        The best match is determined by the highest magnitude weight
        """
        SUBSTRING_WEIGHT = 0.2
        WBEST = None
        sbest = None
        sxv = self._standardize_label(sx.val)
        sxp = self._id_to_ontology(sx.class_id)
        for sy in sys:
            syv = self._standardize_label(sy.val)
            syp = self._id_to_ontology(sy.class_id)
            W = None
            if sxv == syv:
                confidence = sx.confidence * sy.confidence
                if sx.is_abbreviation() or sy.is_abbreviation:
                    confidence *= self._get_config_val(sxp, 'abbreviation_confidence', 0.5)
                    confidence *= self._get_config_val(syp, 'abbreviation_confidence', 0.5)
                W = scope_map[sx.scope()][sy.scope()] + logit(confidence/2)
            elif sxv in syv:
                W = np.array((-SUBSTRING_WEIGHT, SUBSTRING_WEIGHT, 0, 0))
            elif syv in sxv:
                W = np.array((SUBSTRING_WEIGHT, -SUBSTRING_WEIGHT, 0, 0))
            if W is not None:
                # The best match is determined by the highest magnitude weight
                if WBEST is None or max(abs(W)) > max(abs(WBEST)):
                    WBEST = W
                    sbest = sy
        return WBEST, sbest
    
    def weighted_axioms(self, x, y, xg):
        """
        return a tuple (sub,sup,equiv,other) indicating estimated prior probabilities for an interpretation of a mapping
        between x and y.

        See kboom paper
        """
        # TODO: allow additional weighting
        # weights are log odds w=log(p/(1-p))
        # (Sub,Sup,Eq,Other)
        scope_pairs = [
            ('label',   'label',   0.0, 0.0, 3.0,-0.8), 
            ('label',   'exact',   0.0, 0.0, 2.5,-0.5), 
            ('label',   'broad',  -1.0, 1.0, 0.0, 0.0), 
            ('label',   'narrow',  1.0,-1.0, 0.0, 0.0), 
            ('label',   'related', 0.0, 0.0, 0.0, 0.0), 
            ('exact',   'exact',   0.0, 0.0, 2.5,-0.5), 
            ('exact',   'broad',  -1.0, 1.0, 0.0, 0.0), 
            ('exact',   'narrow',  1.0,-1.0, 0.0, 0.0), 
            ('exact',   'related', 0.0, 0.0, 0.0, 0.0), 
            ('related', 'broad',  -0.5, 0.5, 0.0, 0.0), 
            ('related', 'narrow',  0.5,-0.5, 0.0, 0.0), 
            ('related', 'related', 0.0, 0.0, 0.0, 0.0), 
            ('broad',   'broad',   0.0, 0.0, 0.0, 1.0), 
            ('broad',   'narrow', -0.5, 0.5, 0.0, 0.2), 
            ('narrow',  'narrow',  0.0, 0.0, 0.0, 0.0)
        ]
        # populate symmetric lookup matrix
        scope_map = defaultdict(dict)
        for (l,r,w1,w2,w3,w4) in scope_pairs:
            l = l.upper()
            r = r.upper()
            scope_map[l][r] = np.array((w1,w2,w3,w4))
            scope_map[r][l] = np.array((w2,w1,w3,w4))

        # TODO: get prior based on ontology pair
        # cumulative sum of weights
        WS = None
        pfx1 = self._id_to_ontology(x)
        pfx2 = self._id_to_ontology(y)
        for mw in self.config.get('match_weights', []):
            mpfx1 = mw.get('prefix1','')
            mpfx2 = mw.get('prefix2','')
            X = np.array(mw['weights'])
            if mpfx1 == pfx1 and mpfx2 == pfx2:
                WS = X
            elif mpfx2 == pfx1 and mpfx1 == pfx2:
                WS = self._flipweights(X)
            elif mpfx1 == pfx1 and mpfx2 == '' and WS is None:
                WS = X
            elif mpfx2 == pfx1 and mpfx1 == '' and WS is None:
                WS = self._flipweights(X)

        if WS is None:
            WS = np.array((0.0, 0.0, 0.0, 0.0))
        # defaults
        WS += np.array(self.config.get('default_weights', [0.0, 0.0, 1.5, -0.1]))
        logging.info('WS defaults={}'.format(WS))

        for xw in self.config.get('xref_weights', []):
            left = xw.get('left','')
            right = xw.get('right','')
            X = np.array(xw['weights'])
            if x == left and y == right:
                WS += X
                logging.info('MATCH: {} for {}-{}'.format(X, x, y))
            elif y == left and x == right:
                WS += self._flipweights(X)
                logging.info('IMATCH: {}'.format(X))

        smap = self.smap
        # TODO: symmetrical
        WT = np.array((0.0, 0.0, 0.0, 0.0))
        WBESTMAX = np.array((0.0, 0.0, 0.0, 0.0))
        n = 0
        for sx in smap[x]:
            WBEST, _ = self._best_match_syn(sx, smap[y], scope_map)
            if WBEST is not None:
                WT += WBEST
                n += 1
                if max(abs(WBEST)) > max(abs(WBESTMAX)):
                    WBESTMAX = WBEST
        for sy in smap[y]:
            WBEST, _ = self._best_match_syn(sy, smap[x], scope_map)
            if WBEST is not None:
                WT += WBEST
                n += 1
        # average best match
        if n > 0:
            logging.info('Adding BESTMAX={}'.format(WBESTMAX))
            WS += WBESTMAX
                    
        # TODO: xref, many to many
        WS += self._graph_weights(x, y, xg)
        # TODO: include additional defined weights, eg ORDO
        logging.info('Adding WS, gw={}'.format(WS))

        # jaccard similarity
        (ss1,ss2) = xg[x][y][self.SIMSCORES]
        WS[3] += ((1-ss1) + (1-ss2)) / 2

        # reciprocal best hits are higher confidence of equiv
        rs = xg[x][y]['reciprocal_score']
        if rs == 4:
            WS[2] += 0.5
        if rs == 0:
            WS[2] -= 0.2
        
        #P = np.expit(WS)
        P = 1/(1+np.exp(-WS))
        logging.info('Final WS={}, init P={}'.format(WS, P))
        # probs should sum to 1.0
        P = P / np.sum(P)
        return P

    def _graph_weights(self, x, y, xg):
        ont = self.merged_ontology
        xancs = ont.ancestors(x)
        yancs = ont.ancestors(y)
        pfx = self._id_to_ontology(x)
        pfy = self._id_to_ontology(y)
        xns = [n for n in xg.neighbors(y) if n != x and pfx == self._id_to_ontology(n)]
        yns = [n for n in xg.neighbors(x) if n != y and pfy == self._id_to_ontology(n)]
        pweight = 1.0
        W = np.array((0,0,0,0))
        card = '11'
        if len(xns) > 0:
            card = 'm1'
            for x2 in xns:
                if x2 in xancs:
                    W[0] += pweight
                if x in ont.ancestors(x2):
                    W[1] += pweight
        if len(yns) > 0:
            if card == '11':
                card = '1m'
            else:
                card = 'mm'
            for y2 in yns:
                if y2 in yancs:
                    W[1] += pweight
                if y in ont.ancestors(y2):
                    W[0] += pweight

        logging.debug('CARD: {}/{} <-> {}/{} = {} // X={} Y={} // W={}'.format(x,pfx, y,pfy, card, xns, yns, W))
        invcard = card
        if card == '1m':
            invcard = 'm1'
        elif card == 'm1':
            invcard = '1m'
            
        CW = None
        DEFAULT_CW = None
        for cw in self.config.get('cardinality_weights', []):
            if 'prefix1' not in cw and 'prefix2' not in cw:
                if card == cw['cardinality']:
                    DEFAULT_CW = np.array(cw['weights'])
                if invcard == cw['cardinality']:
                    DEFAULT_CW = self._flipweights(np.array(cw['weights']))
            if 'prefix1'  in cw and 'prefix2' in cw:
                if pfx == cw['prefix1'] and pfy == cw['prefix2'] and card == cw['cardinality']:
                    CW = np.array(cw['weights'])
                
                if pfx == cw['prefix2'] and pfy == cw['prefix1']  and invcard == cw['cardinality']:
                    CW = self._flipweights(np.array(cw['weights']))
                    
        if CW is None:
            if DEFAULT_CW is not None:
                CW = DEFAULT_CW
            else:
                if card == '11':
                    CW = np.array((0.0, 0.0, 1.0, 0.0))
                elif card == '1m':
                    CW = np.array((0.6, 0.4, 0.0, 0.0))
                elif card == 'm1':
                    CW = np.array((0.4, 0.6, 0.0, 0.0))
                elif card == 'mm':
                    CW = np.array((0.2, 0.2, 0.0, 0.5))
        return W + CW
    
    def _flipweights(self, W):
        return np.array((W[1],W[0],W[2],W[3]))
    
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
        unmapped_set = set()
        for nid in self.merged_ontology.nodes():
            if nid in xg:
                for (j,edge) in xg[nid].items():
                    rs = edge.get('reciprocal_score',0)
                    if rs < rs_threshold:
                        unmapped_set.add(nid)
            else:
                unmapped_set.add(nid)
        return unmapped_set
    
    def unmapped_dataframe(self, xg, **args):
        unodes = self.unmapped_nodes(xg, **args)
        ont = self.merged_ontology
        eg = ont.equiv_graph()
        items = []
        for n in unodes:
            mapped_equivs = ''
            if n in eg:
                equivs = set(eg.neighbors(n))
                mapped_equivs = list(equivs - unodes)
            items.append(dict(id=n,label=ont.label(n),mapped_equivs=mapped_equivs))
        df = pd.DataFrame(items, columns=['id','label', 'mapped_equivs'])
        df = df.sort_values(["id"])
        return df
            
    # scores a pairwise combination of synonyms. This will be a mix of
    #  * individual confidence in the synonyms themselves
    #  * confidence of equivalence based on scopes
    # TODO: unify this with probabilistic calculation
    def _combine_syns(self, s1,s2):
        cpred = self._combine_preds(s1.pred, s2.pred)
        s = self._pred_score(cpred)
        s *= s1.confidence * s2.confidence
        if s1.is_abbreviation() or s2.is_abbreviation():
            s *= self._get_config_val(self._id_to_ontology(s1.class_id), 'abbreviation_confidence', 0.5)
            s *= self._get_config_val(self._id_to_ontology(s1.class_id), 'abbreviation_confidence', 0.5)
        logging.debug("COMBINED: {} + {} = {}/{}".format(s1,s2,cpred,s))
        return round(s)
    
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
        for (x,y,d) in xg.edges(data=True):
            # xg is a non-directional Graph object.
            # to get a deterministic ordering we use the idpair key
            (x,y) = d['idpair']
            (s1,s2)=d['syns']
            (ss1,ss2)=d['simscores']
            clique = self._in_clique(x, cliques)
            #ancs = nx.ancestors(g,x)
            left_label = ont.label(x)
            right_label = ont.label(y)
            if ont.is_obsolete(x) and not left_label.startwith('obsolete'):
                left_label = "obsolete " + left_label
            if ont.is_obsolete(y) and not right_label.startwith('obsolete'):
                right_label = "obsolete " + right_label

            P = self.weighted_axioms(x,y,xg)
            item = {'left':x, 'left_label':left_label,
                    'right':y, 'right_label':right_label,
                    'score':d['score'],
                    'left_match_type': s1.pred,
                    'right_match_type': s2.pred,
                    'left_match_val': s1.val,
                    'right_match_val': s2.val,
                    'left_simscore':ss1,
                    'right_simscore':ss2,
                    'reciprocal_score':d.get('reciprocal_score',0),
                    'conditional_pr_equiv': d.get('cpr'),
                    'pr_subClassOf': P[0],
                    'pr_superClassOf': P[1],
                    'pr_equivalentTo': P[2],
                    'pr_other': P[3],
                    'left_novel': d.get('left_novel'),
                    'right_novel': d.get('right_novel'),
                    'left_consistent': d.get('left_consistent'),
                    'right_consistent': d.get('right_consistent'),
                    'equiv_clique_size': len(clique)}
            
            items.append(item)

        ix = ['left', 'left_label', 'right', 'right_label',
              'left_match_type', 'right_match_type',
              'left_match_val', 'right_match_val', 
              'score', 'left_simscore', 'right_simscore', 'reciprocal_score',
              'conditional_pr_equiv',
              'pr_subClassOf', 'pr_superClassOf', 'pr_equivalentTo', 'pr_other',
              'left_novel',
              'right_novel',
              'left_consistent',
              'right_consistent',
              'equiv_clique_size']
        df = pd.DataFrame(items, columns=ix)
        df = df.sort_values(["left","score","right"])
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
        for (x,y) in self.merged_ontology.get_graph().edges():
            g.add_edge(x,y)
        for (x,y) in xg.edges():
            g.add_edge(x,y)
            g.add_edge(y,x)
        return list(strongly_connected_components(g))
        
            
        

### MARSHMALLOW SCHEMAS
                        
class ScopeWeightMapSchema(Schema):
    """
    Maps scope predicates (label, hasExactSynonym etc) to weights (0<=1.0).

    Typically labels and exact matches have higher weight, although this
    may vary with ontology
    """
    label = fields.Float(default=1.0, description="weight of label matches")
    hasExactSynonym = fields.Float(default=0.9, description="weight of exact matches")
    hasRelatedSynonym = fields.Float(default=0.0, description="weight of related matches")
    hasBroadSynonym = fields.Float(default=-0.2, description="weight of broad matches")
    hasNarrowSynonym = fields.Float(default=-0.2, description="weight of narrow matches")
    other = fields.Float(default=-0.5, description="weight of other kinds of matches")

class OntologyConfigurationSchema(Schema):
    """
    configuration that is specific to an ontology
    """
    prefix = fields.String(description="prefix of IDs in ontology, e.g. UBERON")
    scope_weight_map = fields.Nested(ScopeWeightMapSchema(), description="local scope-weight map")
    normalized_form_confidence = fields.Float(description="confidence of a synonym value derived via normalization (e.g. canonical ordering of tokens)")
    abbreviation_confidence = fields.Float(default=0.5, description="confidence of an abbreviation")
    
class CardinalityWeights(Schema):
    """
    Weights for different cardinality combinations, 
    """
    prefix1 = fields.String(description="prefix of IDs in ontology, e.g. MA")
    prefix2 = fields.String(description="prefix of IDs in ontology, e.g. ZFA")
    cardinality = fields.String(description="One of 11, 1m, m1 or mm")
    weights = fields.List(fields.Float(), description="Sub/Sup/Eq/Other")

class MatchWeights(Schema):
    """
    Default weights for a pair of ontologies
    """
    prefix1 = fields.String(description="prefix of IDs in ontology, e.g. MA")
    prefix2 = fields.String(description="prefix of IDs in ontology, e.g. ZFA")
    weights = fields.List(fields.Float(), description="Sub/Sup/Eq/Other")
    
class XrefWeights(Schema):
    """
    Default weights for a pair of classes
    """
    left = fields.String(description="ID of first class")
    right = fields.String(description="ID of second class")
    weights = fields.List(fields.Float(), description="Sub/Sup/Eq/Other")
    
class LexicalMapConfigSchema(Schema):
    """
    global configuration
    """
    scope_weight_map = fields.Nested(ScopeWeightMapSchema(), description="global scope-weight map. May be overridden by ontologies")
    ontology_configurations = fields.List(fields.Nested(OntologyConfigurationSchema()), description="configurations that are specific to an ontology")
    normalized_form_confidence = fields.Float(default=0.8, description="confidence of a synonym value derived via normalization (e.g. canonical ordering of tokens)")
    abbreviation_confidence = fields.Float(default=0.5, description="confidence of an abbreviation")
    match_weights = fields.List(fields.Nested(MatchWeights()))
    cardinality_weights = fields.List(fields.Nested(CardinalityWeights()))
    xref_weights = fields.List(fields.Nested(XrefWeights()))
