import networkx

LABEL_OR_EXACT = 'label_or_exact'

class LexicalMapEngine():
    """
    generates lexical matches between pairs of ontology classes
    """
    def __init__(self):
        self.lmap = {}
        self.smap = {}

    def index_ontology(self, ont):
        """
        Adds an ontology to the index
        """
        syns = ont.all_synonyms(include_label=True)
        for syn in syns:
            self.index_synonym(syn, ont)
            # TODO: stem

    def index_synonym(self, syn, ont):
        syn.ontology = ont
        lmap = self.lmap
        smap = self.smap
        v = syn.val
        cid = syn.class_id
        if v not in lmap:
            lmap[v] = []
        lmap[v].append(syn)
        if cid not in smap:
            smap[cid] = []
        smap[cid].append(syn)

    def find_equiv_sets(self):
        return self.lmap

    def get_xref_graph(self):
        g = networkx.MultiGraph()
        for (v,syns) in self.lmap.items():
            for s1 in syns:
                for s2 in syns:
                    if s1.class_id < s2.class_id:
                        g.add_edge(s1.class_id, s2.class_id, syns=(s1,s2))
        xg = networkx.MultiGraph()
        for i in g.nodes():
            for j in networkx.neighbors(g,i):
                best = 0
                bestm = None
                for ix,m in g[i][j].items():
                    (s1,s2) = m['syns']
                    score = self.combine_syns(s1,s2)
                    if score > best:
                        best = score
                        bestm = m
                xg.add_edge(i,j,best=best)

        return xg
    
    def grouped_mappings(self,id):
        g = self.get_xref_graph()
        m = {}
        for n in g.neighbors(id):
            [prefix, local] = n.split(':')
            if prefix not in m:
                m[prefix] = []
            m[prefix].append(n)
        return m

    def trim_xref_graph(self,g):
        g = self.get_xref_graph()
        for n in g.nodes():
            g.neighbors()

    def combine_syns(self, s1,s2):
        cpred = self.combine_preds(s1.pred, s1.pred)
        s = self.pred_score(cpred)
        return s
    
    def rollup(p):
        if p == 'label':
            return LABEL_OR_EXACT
        if p == 'hasExactSynonym':
            return LABEL_OR_EXACT
        return p
    
    def combine_preds(self, p1, p2):
        if p1 == p2:
            return p1
        if rollup(p1) == rollup(p2):
            return rollup(p1)
        return p1 + p2

    def pred_score(self,p):
        if p == 'label':
            return 10
        if p == LABEL_OR_EXACT:
            return 9
        if p == 'hasExactSynonym':
            return 9
        return 5
                        
        
