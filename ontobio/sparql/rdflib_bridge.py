"""
Mapping between native ontology model and rdflib
"""
from ontobio.ontol import Ontology, Synonym
from prefixcommons.curie_util import contract_uri, expand_uri, get_prefixes
from rdflib import Namespace
from rdflib import BNode
from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import RDFS
from rdflib.namespace import OWL
import networkx
import logging

def rdfgraph_to_ontol(rg):
    """
    Return an Ontology object from an rdflib graph object

    Status: Incomplete
    """
    digraph = networkx.MultiDiGraph()
    from rdflib.namespace import RDF
    label_map = {}
    for c in rg.subjects(RDF.type, OWL.Class):
        cid = contract_uri_wrap(c)
        logging.info("C={}".format(cid))
        for lit in rg.objects(c, RDFS.label):
            label_map[cid] = lit.value
            digraph.add_node(cid, label=lit.value)
        for s in rg.objects(c, RDFS.subClassOf):
            # todo - blank nodes
            sid = contract_uri_wrap(s)
            digraph.add_edge(sid, cid, pred='subClassOf')

    logging.info("G={}".format(digraph))
    payload = {
        'graph': digraph,
        #'xref_graph': xref_graph,
        #'graphdoc': obographdoc,
        #'logical_definitions': logical_definitions
    }
            
    ont = Ontology(handle='wd', payload=payload)
    return ont



                
        
def contract_uri_wrap(uri):
    curies = contract_uri(uri)
    if len(curies) > 0:
        return curies[0]
    else:
        return uri
