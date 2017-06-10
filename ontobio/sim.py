import math

class SimEngine():

    def __init__(self,
                 association_set=None,
                 icmap=None):
        self.association_set = association_set
        self.icmap = icmap

    def _get_icmap(self):
        if self.icmap is None:
            icmap = {}
            aset = self.association_set
            num_subjs = len(asset.subjects)
            for n in aset.ontology.nodes():
                num_anns = len(aset.query([n]))
                freq = num_anns / num_subjs
                ic = None
                if freq > 0:
                    ic = -math.log(freq/num_subjs) / math.log(2)
                icmap[n] = ic
            self.icmap = icmap
        return self.icmap
        
    def information_content(self,nid):
        """
        Returns information content for a node
        """
        icmap = self._get_icmap()
        return icmap[nid]
        
    def entity_jaccard_similarity(self,s1,s2):
        """
        Calculate jaccard index of inferred associations of two subjects

        |ancs(s1) /\ ancs(s2)|
        ---
        |ancs(s1) \/ ancs(s2)|

        """
        a1 = self.association_set.inferred_types(s1)
        a2 = self.association_set.inferred_types(s2)
        num_union = len(a1.union(a2))
        if num_union == 0:
            return 0.0
        return len(a1.intersection(a2)) / num_union
    
    def class_jaccard_similarity(self,c1,c2):
        """
        Calculate jaccard index of two classes

        |ancs(c1) /\ ancs(c2)|
        ---
        |ancs(c1) \/ ancs(c2)|

        """
        ont = self.association_set.ontology
        a1 = ont.ancestors(c1,reflexive=True)
        a2 = ont.ancestors(c2,reflexive=True)
        num_union = len(a1.union(a2))
        if num_union == 0:
            return 0.0
        return len(a1.intersection(a2)) / num_union

    def class_resnik_similarity(self,c1,c2):
        """
        Calculate resnik similarty of two classes

        Return
        ------
        (number,list)
            tuple of max_ic and list of MRCAs
        """
        cas = self.common_ancestors(c1,c2)
        pairs = [(a, self.information_content(a)) for a in cas]
        max_ic = 0
        mrcas = []
        for a,ic in pairs:
            if ic > max_ic:
                max_ic = ic
                mrcas = [a]
            elif ic == max_ic:
                mrcas.append(a)
        return max_ic, mrcas
    
