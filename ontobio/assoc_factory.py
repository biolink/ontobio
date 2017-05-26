"""
Factory class for generating association sets based on a variety of handle types.

Currently only supports golr query
"""

import networkx as nx
import logging
import os
import subprocess
import hashlib
from cachier import cachier
import datetime
from ontobio.golr.golr_associations import bulk_fetch
from ontobio.assocmodel import AssociationSet, AssociationSetMetadata
import ontobio.io.gafparser as px
from ontobio.io.gafparser import GafParser

SHELF_LIFE = datetime.timedelta(days=3)

class AssociationSetFactory():
    """
    Factory for creating AssociationSets

    Currently support for golr (GO and Monarch) is provided but other stores possible
    """
    def __init__(self):
        """
        initializes based on an ontology name
        """

    def create(self, ontology=None,subject_category=None,object_category=None,evidence=None,taxon=None,relation=None, file=None, fmt=None):
        """
        creates an AssociationSet

        Currently, this uses an eager binding to a `ontobio.golr` instance. All compact associations for the particular combination
        of parameters are fetched.

        Arguments
        ---------

        ontology:         an `Ontology` object
        subject_category: string representing category of subjects (e.g. gene, disease, variant)
        object_category: string representing category of objects (e.g. function, phenotype, disease)
        taxon:           string holding NCBITaxon:nnnn ID
        
        """
        meta = AssociationSetMetadata(subject_category=subject_category,
                                      object_category=object_category,
                                      taxon=taxon)
        
        if file is not None:
            return self.create_from_file(file=file,
                                         fmt=fmt,
                                         ontology=ontology,
                                         meta=meta)

        logging.info("Fetching assocs from store")
        assocs = bulk_fetch_cached(subject_category=subject_category,
                                   object_category=object_category,
                                   evidence=evidence,
                                   taxon=taxon)

        logging.info("Creating map for {} subjects".format(len(assocs)))

        
        
        amap = {}
        subject_label_map = {}
        for a in assocs:
            rel = a['relation']
            subj = a['subject']
            subject_label_map[subj] = a['subject_label']
            amap[subj] = a['objects']

            
        aset = AssociationSet(ontology=ontology,
                              meta=meta,
                              subject_label_map=subject_label_map,
                              association_map=amap)
        return aset

    def create_from_tuples(self, tuples, **args):
        """
        Creates from a list of (subj,subj_name,obj) tuples
        """
        amap = {}
        subject_label_map = {}
        for a in tuples:
            subj = a[0]
            subject_label_map[subj] = a[1]
            if subj not in amap:
                amap[subj] = []
            amap[subj].append(a[2])
        
        aset = AssociationSet(subject_label_map=subject_label_map, association_map=amap, **args)
        return aset
    
    def create_from_file(self, file=None, fmt='gaf', **args):
        """
        Creates from a file.

        Arguments
        ---------
        file : str or file
            input file or filename
        format : str
            name of format e.g. gaf
        
        """
        if isinstance(file,str):
            file = open(file,"r")

        p = None
        if fmt == 'gaf':
            p = px.GafParser()
        elif fmt == 'gpad':
            p = px.GpadParser()
        elif fmt == 'hpoa':
            p = px.HpoaParser()
        else:
            logging.error("Format not recognized: {}".format(fmt))
        logging.info("Parsing {} with {}/{}".format(file, fmt, p))
        results = p.skim(file)
        return self.create_from_tuples(results, **args)
    
    def create_from_gaf(self, file, **args):
        """
        Creates from a GAF file
        """
        p = GafParser()
        results = p.skim(file)
        return self.create_from_tuples(results, **args)


    def create_from_phenopacket(self, file):
        """
        Creates from a phenopacket file
        """
        pass

    def create_from_simple_json(self, file):
        """
        Creates from a simple json rendering
        """
        pass


@cachier(stale_after=SHELF_LIFE)
def bulk_fetch_cached(**args):
        logging.info("Fetching assocs from store (will be cached)")
        return bulk_fetch(**args)
    
