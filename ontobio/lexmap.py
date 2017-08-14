"""
Lexical mapping of ontology classes
"""
import networkx
import logging
import re
from ontobio.ontol import Synonym, Ontology
from collections import defaultdict


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
    def __init__(self, nweight=1.0, wsmap=default_wsmap()):
        """
        Arguments
        ---------
        nweight: double
            weight to apply to any normalized lexical values
        wdmap: dict
            maps words to normalized synonyms.
        """
        # maps label or syn value to Synonym object
        self.lmap = {}
        # maps node id to synonym objects
        self.smap = {}
        self.nweight = nweight
        self.wsmap = wsmap
        self.npattern = re.compile('[\W_]+')
        self.exclude_obsolete = True
        self.ontology_pairs = None
        self.id_to_ontology_map = defaultdict(list)
        self.merged_ontology = Ontology()

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
        logging.info("Indexing {} syns in {}".format(len(syns),ont))
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
            logging.debug("Incomplete syn: {}".format(syn))
            return
        if self.exclude_obsolete and ont.is_obsolete(syn.class_id):
            return
        syn.ontology = ont
        v = syn.val.lower()
        nv = self._normalize(v, self.wsmap)
        if self.nweight > 0:
            self._index_synonym_val(syn, v)
            if nv != v:
                nsyn = Synonym(syn.class_id,
                               val=syn.val,
                               pred=syn.pred,
                               lextype=syn.lextype,
                               ontology=ont)
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

        
    def find_equiv_sets(self):
        return self.lmap

    def get_xref_graph(self):
        """
        Generate mappings based on lexical properties and return as networkx graph.

        Algorithm
        ~~~~~~~~~

        - A dictionary is stored between ref:`Synonym` values and synonyms. See ref:`index_synonym`.
          Note that Synonyms include the primary label

        - Each key in the dictionary is examined to determine if there exist two Synonyms from
          different ontology classes

        This avoids N^2 pairwise comparisons: instead the time taken is linear

        Edge properties
        ~~~~~~~~~~~~~~~
        The return object is a networkx graph, connecting pairs of ontology classes.

        Edges are annotated with metadata about how the match was found:

        syns: pair
            pair of `Synonym` objects, corresponding to the synonyms for the two nodes
        score: int
            score indicating strength of mapping, between 0 and 100

        Returns
        -------
        MultiDiGraph
            networkx multigraph (directional)
        """

        # initial graph; all matches
        g = networkx.MultiGraph()

        # lmap collects all syns by token
        for (v,syns) in self.lmap.items():
            for s1 in syns:
                for s2 in syns:
                    if self._is_comparable(s1,s2):
                        g.add_edge(s1.class_id, s2.class_id, syns=(s1,s2))

        # graph of best matches
        # TODO: configurability
        xg = networkx.MultiDiGraph()
        for i in g.nodes():
            for j in networkx.neighbors(g,i):
                best = 0
                bestm = None
                for ix,m in g[i][j].items():
                    (s1,s2) = m['syns']
                    score = self._combine_syns(s1,s2)
                    if score > best:
                        best = score
                        bestm = m
                if not xg.has_edge(i,j):
                    syns = g[i][j][0]['syns']
                    xg.add_edge(i,j,score=best,syns=syns)

        return xg

    # true if syns s1 and s2 should be compared.
    #  - if ontology_pairs is set, then only consider (s1,s2) if their respective source ontologies are in the list of pairs
    #  - otherwise compare all classes, but only in one direction
    def _is_comparable(self, s1, s2):
        if s1.class_id == s2.class_id:
            return False
        if self.ontology_pairs is not None:
            logging.debug('TEST: {}{} in {}'.format(s1.ontology.id, s2.ontology.id, self.ontology_pairs))
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
        for (i,j,d) in xg.edges_iter(data=True):
            #ancs1 = ont.ancestors(i) + ont.descendants(i)
            #ancs2 = ont.ancestors(j) + ont.descendants(j)
            ancs1 = self._blanket(i)
            ancs2 = self._blanket(j)
            s1 = self._sim(xg, ancs1, ancs2)
            s2 = self._sim(xg, ancs2, ancs1)
            s = 1 - ((1-s1) * (1-s2))
            logging.debug("Score {} x {} = {} x {} = {} // {}".format(i,j,s1,s2,s, d))
            xg[i][j][0]['lexscore'] = xg[i][j][0]['score']
            xg[i][j][0]['simscores'] = (s1,s2)
            xg[i][j][0]['score'] *= s

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
            score = xg[nid][x][0]['score']
            for ont in self.id_to_ontology_map[x]:
                xrefmap[ont.id].append( (score,x) )
        return xrefmap
        
    def assign_best_matches(self, xg):
        for i in xg.nodes():
            xrefmap = self._neighbors_by_ontology(xg, i)
            for (ontid,pairs) in xrefmap.items():
                pairs.sort()
                (bscore,bx) = pairs[0]
                logging.info("BEST: {}".format(bx))
                # TODO: refactor for directional
                xg[bx][i][0]['is_bestA'] = True
                xg[i][bx][0]['is_bestB'] = True
        
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

    def _combine_syns(self, s1,s2):
        cpred = self._combine_preds(s1.pred, s1.pred)
        s = self._pred_score(cpred)
        logging.debug("{} + {} = {}/{}".format(s1,s2,cpred,s))
        return s
    
    def _rollup(p):
        if p == 'label':
            return LABEL_OR_EXACT
        if p == 'hasExactSynonym':
            return LABEL_OR_EXACT
        return p
    
    def _combine_preds(self, p1, p2):
        if p1 == p2:
            return p1
        if _rollup(p1) == _rollup(p2):
            return _rollup(p1)
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
                        
        
