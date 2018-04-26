"""Simple association model

The core class here is AssociationSet, a holder for a set of
associations between entities such as genes and ontology
classes. AssociationSets can also be throught of as subsuming
traditional 'gene sets'

The model is deliberately simple, and does not seek to represent
metadata about the association - it is assumed that this is handled
upstream. See the assoc_factory module for details - this allows the
client to create an association set based on various criteria such as
taxa of interest or evidence criteria.

"""
import logging
import scipy.stats # TODO - move
import scipy as sp # TODO - move
import pandas as pd

class UnknownSubjectException(Exception):
    pass

class AssociationSet():
    """An object that represents a collection of associations

    NOTE: the intention is that this class can be subclassed to provide
    either high-efficiency implementations, or implementations backed by services or external stores.
    The default implementation is in-memory.

    """

    def __init__(self, ontology=None, association_map=None, subject_label_map=None, meta=None):
        """
        NOTE: in general you do not need to call this yourself. See assoc_factory

        initializes an association set, which minimally consists of:

         - an ontology (e.g. GO, HP)
         - a map between subjects (e.g genes) and sets/lists of term IDs

        """
        self.ontology = ontology
        self.association_map = association_map
        self.subject_label_map = subject_label_map
        self.subject_to_inferred_map = {}
        self.meta = meta  # TODO
        self.associations_by_subj = None
        self.associations_by_subj_obj = None
        self.strict = False
        self.index()

        if self.association_map is None:
            self.association_map = {}

        logging.info("Created {}".format(self))

    def __str__(self):
        imap = self.subject_to_inferred_map
        return "AssocSet |S|={} |S->I|={}".format(len(imap.keys()), len(imap.items()))

    def index(self):
        """
        Creates indexes based on inferred terms.

        You do not need to call this yourself; called on initialization
        """
        self.subjects = list(self.association_map.keys())

        # ensure annotations unique
        for (subj,terms) in self.association_map.items():
            self.association_map[subj] = list(set(self.association_map[subj]))
            
        logging.info("Indexing {} items".format(len(self.subjects)))
        n = 0
        all_objs = set()
        for (subj,terms) in self.association_map.items():
            ancs = self.termset_ancestors(terms)
            all_objs.update(ancs)
            self.subject_to_inferred_map[subj] = ancs
            n = n+1
            if n<5:
                logging.info(" Indexed: {} -> {}".format(subj, ancs))
            elif n == 6:
                logging.info("[TRUNCATING>5]....")
        self.objects = all_objs

    def inferred_types(self, subj):
        """
        Returns: set of reflexive inferred types for a subject.

        E.g. if a gene is directly associated with terms A and B, and these terms have ancestors C, D and E
        then the set returned will be {A,B,C,D,E}
        
        Arguments
        ---------

          subj - ID string

        Returns: set of class IDs

        """
        if subj in self.subject_to_inferred_map:
            return self.subject_to_inferred_map[subj]
        if self.strict:
            raise UnknownSubjectException(subj)
        else:
            return set([])
        
    def termset_ancestors(self, terms):
        """
        reflexive ancestors

        Arguments
        ---------

          terms - a set or list of class IDs

        Returns: set of class IDs
        """
        ancs = set()
        for term in terms:
            ancs = ancs.union(self.ontology.ancestors(term))
        return ancs.union(set(terms))

    def query_associations(self, subjects=None, infer_subjects=True, include_xrefs=True):
        """
        Query for a set of associations.

        Note: only a minimal association model is stored, so all results are returned as (subject_id,class_id) tuples

        Arguments:

         subjects: list

          list of subjects (e.g. genes, diseases) used to query associations. Any association to one of these subjects or
          a descendant of these subjects (assuming infer_subjects=True) are returned.

         infer_subjects: boolean (default true)

          See above

         include_xrefs: boolean (default true)

          If true, then expand inferred subject set to include all xrefs of those subjects.

        Example: if a high level disease node (e.g. DOID:14330 Parkinson disease) is specified, then the default behavior
        (infer_subjects=True, include_xrefs=True) and the ontology includes DO, results will include associations from 
        both descendant DOID classes, and all xrefs (e.g. OMIM)

        """
        if subjects is None:
            subjects = []
        mset = set()
        if infer_subjects:
            for subj in subjects:
                mset.update(self.ontology.descendants(subj))
        mset.update(set(subjects))
        if include_xrefs:
            xset = set()
            for m in mset:
                xrefs = self.ontology.xrefs(m, bidirectional=True)
                if xrefs is not None:
                    xset.update(xrefs)
            mset.update(xset)
        logging.debug("Matching subjects: {}".format(mset))
        mset = mset.intersection(self.subjects)
        logging.debug("Matching subjects with anns: {}".format(mset))
        amap = self.association_map
        results = []
        for m in mset:
            if m in amap:
                for t in amap[m]:
                    results.append( (m,t) )
        return results

    def annotations(self, subject_id):
        """
        Returns a list of classes used to describe a subject

        @Deprecated: use objects_for_subject
        """
        if subject_id in self.association_map:
            return self.association_map[subject_id]
        else:
            return []

    def objects_for_subject(self, subject_id):
        """
        Returns a list of classes used to describe a subject
        """
        if subject_id in self.association_map:
            return self.association_map[subject_id]
        else:
            return []
        
    def query(self, terms=None, negated_terms=None):
        """
        Basic boolean query, using inference.

        Arguments:

         - terms: list

             list of class ids. Returns the set of subjects that have at least one inferred annotation to each of the specified classes.

         - negated_terms: list

             list of class ids. Filters the set of subjects so that there are no inferred annotations to any of the specified classes
        """

        if terms is None:
            terms = []
        matches_all = 'owl:Thing' in terms
        if negated_terms is None:
            negated_terms = []
        termset = set(terms)
        negated_termset = set(negated_terms)
        matches = []
        n_terms = len(termset)
        for subj in self.subjects:
            if matches_all or len(termset.intersection(self.inferred_types(subj))) == n_terms:
                if len(negated_termset.intersection(self.inferred_types(subj))) == 0:
                    matches.append(subj)
        return matches

    def query_intersections(self, x_terms=None, y_terms=None, symmetric=False):
        """
        Query for intersections of terms in two lists

        Return a list of intersection result objects with keys:
         - x : term from x
         - y : term from y
         - c : count of intersection
         - j : jaccard score
        """
        if x_terms is None:
            x_terms = []
        if y_terms is None:
            y_terms = []
        xset = set(x_terms)
        yset = set(y_terms)
        zset = xset.union(yset)

        # first built map of gene->termClosure.
        # this could be calculated ahead of time for all g,
        # but this may be space-expensive. TODO: benchmark
        gmap={}
        for z in zset:
            gmap[z] = []
        for subj in self.subjects:
            ancs = self.inferred_types(subj)
            for a in ancs.intersection(zset):
                gmap[a].append(subj)
        for z in zset:
            gmap[z] = set(gmap[z])
        ilist = []
        for x in x_terms:
            for y in y_terms:
                if not symmetric or x<y:
                    shared = gmap[x].intersection(gmap[y])
                    union = gmap[x].union(gmap[y])
                    j = 0
                    if len(union)>0:
                        j = len(shared) / len(union)
                    ilist.append({'x':x,'y':y,'shared':shared, 'c':len(shared), 'j':j})
        return ilist

    @staticmethod
    def intersectionlist_to_matrix(ilist, xterms, yterms):
        """
        WILL BE DEPRECATED

        Replace with method to return pandas dataframe
        """
        z = [ [0] * len(xterms) for i1 in range(len(yterms)) ]
    
        xmap = {}
        xi = 0
        for x in xterms:
            xmap[x] = xi
            xi = xi+1
        
        ymap = {}
        yi = 0
        for y in yterms:
            ymap[y] = yi
            yi = yi+1
            
        for i in ilist:
            z[ymap[i['y']]][xmap[i['x']]] = i['j']
            
        logging.debug("Z={}".format(z))
        return (z,xterms,yterms)
    
    def as_dataframe(self, fillna=True, subjects=None):
        """
        Return association set as pandas DataFrame

        Each row is a subject (e.g. gene)
        Each column is the inferred class used to describe the subject
        """
        entries = []
        selected_subjects = self.subjects
        if subjects is not None:
            selected_subjects = subjects
            
        for s in selected_subjects:
            vmap = {}
            for c in self.inferred_types(s):
                vmap[c] = 1
            entries.append(vmap)
        logging.debug("Creating DataFrame")
        df = pd.DataFrame(entries, index=selected_subjects)
        if fillna:
            logging.debug("Performing fillna...")
            df = df.fillna(0)
        return df

    def label(self, id):
        """
        return label for a subject id

        Will make use of both the ontology and the association set
        """
        if self.ontology is not None:
            label = self.ontology.label(id)
            if label is not None:
                return label
        if self.subject_label_map is not None and id in self.subject_label_map:
            return self.subject_label_map[id]
        return None

    def subontology(self, minimal=False):
        """
        Generates a sub-ontology based on associations
        """
        return self.ontology.subontology(self.objects, minimal=minimal)

    def associations(self, subject, object=None):
        """
        Given a subject-object pair (e.g. gene id to ontology class id), return all association
        objects that match.

        """
        if object is None:
            if self.associations_by_subj is not None:
                return self.associations_by_subj[subject]
            else:
                return []
        else:
            if self.associations_by_subj_obj is not None:
                return self.associations_by_subj_obj[(subject,object)]
            else:
                return []

    # TODO: consider moving to other module
    def enrichment_test(self, subjects=None, background=None, hypotheses=None, threshold=0.05, labels=False, direction='greater'):
        """
        Performs term enrichment analysis. 

        Arguments
        ---------

        subjects: string list

            Sample set. Typically a gene ID list. These are assumed to have associations

        background: string list

            Background set. If not set, uses full set of known subject IDs in the association set

        threshold: float

            p values above this are filtered out

        labels: boolean

            if true, labels for enriched classes are included in result objects

        direction: 'greater', 'less' or 'two-sided'

            default is greater - i.e. enrichment test. Use 'less' for depletion test.

        """
        if subjects is None:
            subjects = []

        subjects=set(subjects)
        bg_count = {}
        sample_count = {}
        potential_hypotheses = set()
        sample_size = len(subjects)
        for s in subjects:
            potential_hypotheses.update(self.inferred_types(s))
        if hypotheses is None:
            hypotheses = potential_hypotheses
        else:
            hypotheses = potential_hypotheses.intersection(hypotheses)
        logging.info("Hypotheses: {}".format(hypotheses))
        
        # get background counts
        # TODO: consider doing this ahead of time
        if background is None:
            background = set(self.subjects)
        else:
            background = set(background)

        # ensure background includes all subjects
        background.update(subjects)
        
        bg_size = len(background)
        
        for c in hypotheses:
            bg_count[c] = 0
            sample_count[c] = 0
        for s in background:
            ancs = self.inferred_types(s)
            for a in ancs.intersection(hypotheses):
                bg_count[a] = bg_count[a]+1
        for s in subjects:
            for a in self.inferred_types(s):
                if a in hypotheses:
                    sample_count[a] = sample_count[a]+1

        hypotheses = [x for x in hypotheses if bg_count[x] > 1]
        logging.info("Filtered hypotheses: {}".format(hypotheses))
        num_hypotheses = len(hypotheses)
                
        results = []
        for cls in hypotheses:
            
            # https://en.wikipedia.org/wiki/Fisher's_exact_test
            #
            #              Cls  NotCls    RowTotal
            #              ---  ------    ---
            # study/sample [a,      b]    sample_size
            # rest of ref  [c,      d]    bg_size - sample_size
            #              ---     ---
            #              nCls  nNotCls

            a = sample_count[cls]
            b = sample_size - a
            c = bg_count[cls] - a
            d = (bg_size - bg_count[cls]) - b
            #logging.debug("ABCD="+str((cls,a,b,c,d,sample_size)))
            _, p_uncorrected = sp.stats.fisher_exact( [[a, b], [c, d]], direction)
            p = p_uncorrected * num_hypotheses
            if p>1.0:
                p=1.0
            #logging.debug("P={} uncorrected={}".format(p,p_uncorrected))
            if p<threshold:
                res = {'c':cls,'p':p,'p_uncorrected':p_uncorrected}
                if labels:
                    res['n'] = self.ontology.label(cls)
                results.append(res)
            
        results = sorted(results, key=lambda x:x['p'])
        return results
            
    def jaccard_similarity(self,s1,s2):
        """
        Calculate jaccard index of inferred associations of two subjects

        |ancs(s1) /\ ancs(s2)|
        ---
        |ancs(s1) \/ ancs(s2)|

        """
        a1 = self.inferred_types(s1)
        a2 = self.inferred_types(s2)
        num_union = len(a1.union(a2))
        if num_union == 0:
            return 0.0
        return len(a1.intersection(a2)) / num_union

    def similarity_matrix(self, x_subjects=None, y_subjects=None, symmetric=False):
        """
        Query for similarity matrix between groups of subjects

        Return a list of intersection result objects with keys:
         - x : term from x
         - y : term from y
         - c : count of intersection
         - j : jaccard score
        """
        if x_subjects is None:
            x_subjects = []
        if y_subjects is None:
            y_subjects = []

        xset = set(x_subjects)
        yset = set(y_subjects)
        zset = xset.union(yset)

        # first built map of gene->termClosure.
        # this could be calculated ahead of time for all g,
        # but this may be space-expensive. TODO: benchmark
        gmap={}
        for z in zset:
            gmap[z] = self.inferred_types(z)
        ilist = []
        for x in x_subjects:
            for y in y_subjects:
                if not symmetric or x<y:
                    shared = gmap[x].intersection(gmap[y])
                    union = gmap[x].union(gmap[y])
                    j = 0
                    if len(union)>0:
                        j = len(shared) / len(union)
                    ilist.append({'x':x,'y':y,'shared':shared, 'c':len(shared), 'j':j})
        return self.intersectionlist_to_matrix(ilist, x_subjects, y_subjects)
    

class NamedEntity():
    """
    E.g. a gene etc
    """

    def __init__(self, id, label=None, taxon=None):
        self.id=id
        self.label=label
        self.taxon=taxon

class AssociationSetMetadata():
    """
    Information about how an association set is derived
    """

    def __init__(self, id=None, taxon=None, evidence=None, subject_category=None, object_category=None):
        self.id=id
        self.taxon=taxon
        
