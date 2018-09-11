"""
Semantic Search (ALPHA)
"""
from typing import Union, List, Dict, Set, Optional, Tuple
from collections import defaultdict
import math
import logging

import pandas as pd
import numpy as np
from scipy.spatial.distance import cosine
import networkx.algorithms.traversal.depth_first_search as dfs
import networkx as nx

ClassId = str
SubjectId = str
SimScore = float
ICValue = float
InformationContent = float

class SemSearchEngine(object):
    """
    A semantic search engine can be used to compare individual annotated entities,
    or to compare pairs of entities.

    It wraps an assocmodel
    """
    
    def __init__(self, assocmodel=None):
        self.assocmodel = assocmodel # type: AssociationSet
        self.assoc_df = assocmodel.as_dataframe()
        # TODO: test for cyclicity
        self.G = assocmodel.ontology.get_graph()
        self.ics = None # Optional
        # TODO: class x class df
        self.ancmap = {}
        for c in self.G.nodes():
            self.ancmap[c] = nx.ancestors(self.G, c)

    def pw_score_jaccard(self, s1 : ClassId, s2 : ClassId) -> SimScore:
        """
        Calculate jaccard index of inferred associations of two subjects

        |ancs(s1) /\ ancs(s2)|
        ---
        |ancs(s1) \/ ancs(s2)|

        """
        am = self.assocmodel
        a1 = am.inferred_types(s1)
        a2 = am.inferred_types(s2)
        num_union = len(a1 | a2)
        if num_union == 0:
            return 0.0
        return len(a1 & a2) / num_union

    def pw_score_cosine(self, s1 : ClassId, s2 : ClassId) -> SimScore:
        """
        Cosine similarity of two subjects

        Arguments
        ---------
        s1 : str
            class id


        Return
        ------
        number
            A number between 0 and 1
        """
        df = self.assoc_df
        slice1 = df.loc[s1].values
        slice2 = df.loc[s2].values
        return 1 - cosine(slice1, slice2)
    
    def calculate_all_information_content(self) -> pd.Series:
        """
        Calculate the Information Content (IC) value of every class

        Sets the internal icmap cache and returns an array 

        Return
        ------
        Series
            a pandas Series indexed by class id and with IC as value
        """
        logging.info("Calculating all class ICs")
        df = self.assoc_df
        freqs = df.sum(axis=0)
        n_subjects, _ = df.shape
        ics = freqs.apply(lambda x: -math.log(x / n_subjects)/math.log(2))
        self.ics = ics
        logging.info("DONE calculating all class ICs")
        return ics

    def _information_content_frame(self) -> pd.Series:
        if self.ics == None:
            self.calculate_all_information_content()
        return self.ics

    def _ancestors(self, c1 : ClassId) -> Set[ClassId]:
        return self.ancmap[c1]

    def calculate_mrcas(self, c1 : ClassId, c2 : ClassId) -> Set[ClassId]:
        """
        Calculate the MRCA for a class pair
        """
        G = self.G
        # reflexive ancestors
        ancs1 = self._ancestors(c1) | {c1}
        ancs2 = self._ancestors(c2) | {c2}
        common_ancestors = ancs1 & ancs2
        redundant = set()
        for a in common_ancestors:
            redundant = redundant | nx.ancestors(G, a)
        return common_ancestors - redundant

    #def calculate_mrcas_ic(self, c1 : ClassId, c2 : ClassId) -> InformationContent, Set[ClassId]:
    #    mrcas = self.calculate_mrcas(c1, c2)
        
    
    def calculate_all_micas(self):
        """
        Calculate the MICA (Most Informative Common Ancestor) of every class-pair
        """
        G = self.G
        ics = self._information_content_frame()
        classes = list(dfs.dfs_preorder_nodes(G))
        #mica_df = pd.DataFrame(index=classes, columns=classes)
        #mica_ic_df = pd.DataFrame(index=classes, columns=classes)
        ncs = len(classes)
        ic_grid = np.empty([ncs,ncs])
        mica_arrs = []
        logging.info('Calculating ICs for {} x {} classes'.format(ncs, ncs))
        for c1i in range(0,ncs):
            c1 = classes[c1i]
            logging.debug('Calculating ICs for {}'.format(c1))
            ancs1r = self._ancestors(c1) | {c1}
            c2i = 0
            mica_arr = []            
            for c2i in range(0,ncs):
                c2 = classes[c2i]
                # TODO: optimize; matrix is symmetrical
                #if c1i > c2i:
                #    continue
                ancs2r = self._ancestors(c2) | {c2}
                common_ancs = ancs1r & ancs2r
                if len(common_ancs) > 0:
                    ic_cas = ics.loc[common_ancs]
                    max_ic = float(ic_cas.max())
                    ic_micas = ic_cas[ic_cas >= max_ic]
                    micas = set(ic_micas.index)
                    mica_arr.append(micas)
                    #mica_grid[c1i, c2i] = micas
                    #mica_grid[c2i, c1i] = micas
                    ic_grid[c1i, c2i] = max_ic
                    #ic_grid[c2i, c1i] = max_ic
                else:
                    ic_grid[c1i, c2i] = 0
                    mica_arr.append(set())
                    #ic_grid[c2i, c1i] = 0
                    # TODO: consider optimization step; blank out all anc pairs
            mica_arrs.append(mica_arr)
        logging.info('DONE Calculating ICs for {} x {} classes'.format(ncs, ncs))
        #self.mica_df = pd.DataFrame(mica_grid, index=classes, columns=classes)
        self.mica_df = pd.DataFrame(mica_arrs, index=classes, columns=classes)
        self.mica_ic_df = pd.DataFrame(ic_grid, index=classes, columns=classes)

    def pw_score_resnik_bestmatches(self, s1: SubjectId, s2: SubjectId) -> Tuple[ICValue, ICValue, ICValue]:
        am = self.assocmodel
        return self.pw_compare_class_sets(am.annotations(s1), am.annotations(s2))
        
    def pw_compare_class_sets(self, cset1: Set[ClassId], cset2: Set[ClassId]) -> Tuple[ICValue, ICValue, ICValue]:
        """
        Compare two class profiles
        """
        pairs = self.mica_ic_df.loc[cset1, cset2]
        max0 = pairs.max(axis=0)
        max1 = pairs.max(axis=1)
        idxmax0 = pairs.idxmax(axis=0)
        idxmax1 = pairs.idxmax(axis=1)
        mean0 = max0.mean()
        mean1 = max1.mean()
        return (mean0+mean1)/2, mean0, mean1
        #return (mean0+mean1)/2, mean0, mean1, idxmax0, idxmax1
        
    def search(self, cset: Set[ClassId]):
        slice = self.mica_ic_df.loc[cset]
        am = self.assocmodel
        for i in am.subjects:
            pass # TODO
    
