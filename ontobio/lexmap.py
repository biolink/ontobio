"""
Lexical mapping of ontology classes
"""
import networkx
import logging
import re
from ontobio.ontol import Synonym

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

    def index_ontology(self, ont):
        """
        Adds an ontology to the index
        """
        syns = ont.all_synonyms(include_label=True)
        logging.info("Indexing {} syns in {}".format(len(syns),ont))
        for syn in syns:
            self.index_synonym(syn, ont)
            # TODO: stem

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

        Edges are annotated with metadata about how match was found

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
                    # TODO: allow configuration of which takes precedence
                    if s1.class_id < s2.class_id:
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
                    xg.add_edge(i,j,best=best,syns=syns)

        return xg
    
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
            return 10
        if p == LABEL_OR_EXACT:
            return 9
        if p == 'hasExactSynonym':
            return 9
        return 5
                        
        
