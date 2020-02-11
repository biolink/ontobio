"""
Factory class for generating ontology objects based on a variety of handle types.

See :ref:`inputs` on readthedocs for more details
"""

import ontobio.obograph_util as obograph_util
from ontobio.ontol import Ontology
from ontobio.sparql.sparql_ontology import EagerRemoteSparqlOntology
import os
import subprocess
import hashlib
import logging

logger = logging.getLogger(__name__)

# TODO
default_ontology_handle = 'cache/ontologies/pato.json'
#if not os.path.isfile(ontology_handle):
#    ontology_handle = None

global default_ontology
default_ontology = None


class OntologyFactory():
    """Implements a factory for generating :class:`Ontology` objects.

    You should use a factory object rather than initializing
    `Ontology` directly. See :ref:`inputs` for more details.
    """

    # class variable - reuse the same object throughout
    test = 0

    def __init__(self, handle=None):
        """
        initializes based on an ontology name

        Arguments
        ---------
        handle : str
            see `create`
        """
        self.handle = handle

    def create(self, handle=None, handle_type=None, **args):
        """
        Creates an ontology based on a handle

        Handle is one of the following

        - `FILENAME.json` : creates an ontology from an obographs json file
        - `obo:ONTID`     : E.g. obo:pato - creates an ontology from obolibrary PURL (requires owltools)
        - `ONTID`         : E.g. 'pato' - creates an ontology from a remote SPARQL query

        Arguments
        ---------
        handle : str
            specifies how to retrieve the ontology info

        """
        if handle is None:
            self.test = self.test+1
            logger.info("T: "+str(self.test))
            global default_ontology
            if default_ontology is None:
                logger.info("Creating new instance of default ontology")
                default_ontology = create_ontology(default_ontology_handle, **args)
            logger.info("Using default_ontology")
            return default_ontology
        return create_ontology(handle, **args)

def create_ontology(handle=None, **args):
    ont = None
    logger.info("Determining strategy to load '{}' into memory...".format(handle))

    if handle.find("+") > -1:
        handles = handle.split("+")
        onts = [create_ontology(ont) for ont in handles]
        ont = onts.pop()
        ont.merge(onts)
        return ont

    # TODO: consider replacing with plugin architecture
    if handle.find(".") > 0 and os.path.isfile(handle):
        logger.info("Fetching obograph-json file from filesystem")
        ont = translate_file_to_ontology(handle, **args)
    elif handle.startswith("obo:"):
        logger.info("Fetching from OBO PURL")
        if handle.find(".") == -1:
            if handle == 'chebi' or handle == 'ncbitaxon' or handle == 'pr':
                handle += '.obo'
                logger.info("using obo for large ontology: {}".format(handle))
            else:
                handle += '.owl'
        fn = '/tmp/'+handle
        if not os.path.isfile(fn):
            url = handle.replace("obo:","http://purl.obolibrary.org/obo/")
            cmd = ['owltools',url,'-o','-f','json',fn]
            cp = subprocess.run(cmd, check=True)
            logger.info(cp)
        else:
            logger.info("using cached file: "+fn)
        g = obograph_util.convert_json_file(fn)
        ont = Ontology(handle=handle, payload=g)
    elif handle.startswith("wdq:"):
        from ontobio.sparql.wikidata_ontology import EagerWikidataOntology
        logger.info("Fetching from Wikidata")
        ont = EagerWikidataOntology(handle=handle)
    elif handle.startswith("skos:"):
        fn = handle.replace('skos:','')
        from ontobio.sparql.skos import Skos
        logger.info("Fetching from Skos file")
        skos = Skos()
        ont = skos.process_file(fn)
    elif handle.startswith("scigraph:"):
        from ontobio.neo.scigraph_ontology import RemoteScigraphOntology
        logger.info("Fetching from SciGraph")
        ont = RemoteScigraphOntology(handle=handle)
    elif handle.startswith("http:"):
        logger.info("Fetching from Web PURL: "+handle)
        encoded = hashlib.sha256(handle.encode()).hexdigest()
        #encoded = binascii.hexlify(bytes(handle, 'utf-8'))
        #base64.b64encode(bytes(handle, 'utf-8'))
        logger.info(" encoded: "+str(encoded))
        fn = '/tmp/'+encoded
        if not os.path.isfile(fn):
            cmd = ['owltools',handle,'-o','-f','json',fn]
            cp = subprocess.run(cmd, check=True)
            logger.info(cp)
        else:
            logger.info("using cached file: "+fn)
        g = obograph_util.convert_json_file(fn)
        ont = Ontology(handle=handle, payload=g)
    else:
        logger.info("Fetching from SPARQL")
        ont = EagerRemoteSparqlOntology(handle=handle)
        #g = get_digraph(handle, None, True)
    return ont

def create_ontology_from_obograph(og):
    ont = None
    g = obograph_util.convert_json_object(og)
    ont = Ontology(handle=None, payload=g)
    return ont

def translate_file_to_ontology(handle, **args):
    if handle.endswith(".json"):
        g = obograph_util.convert_json_file(handle, **args)
        return Ontology(handle=handle, payload=g)
    elif handle.endswith(".ttl"):
        from ontobio.sparql.rdf2nx import RdfMapper
        logger.info("RdfMapper: {}".format(args))
        m = RdfMapper(**args)
        return m.convert(handle,'ttl')
    else:
        if not (handle.endswith(".obo") or handle.endswith(".owl")):
            logger.info("Attempting to parse non obo or owl file with owltools: "+handle)
        encoded = get_checksum(handle)
        logger.info(" encoded: "+str(encoded))
        fn = '/tmp/'+encoded
        if not os.path.isfile(fn):
            cmd = ['owltools',handle,'-o','-f','json',fn]
            cp = subprocess.run(cmd, check=True)
            logger.info(cp)
        else:
            logger.info("using cached file: "+fn)
        g = obograph_util.convert_json_file(fn, **args)
        return Ontology(handle=handle, payload=g)

def get_checksum(file):
    """
    Get SHA256 hash from the contents of a given file
    """
    with open(file, 'rb') as FH:
        contents = FH.read()
    return hashlib.sha256(contents).hexdigest()
