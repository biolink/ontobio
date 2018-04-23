import logging
import requests

import rdflib
from rdflib import Namespace
from rdflib.namespace import RDF
from rdflib.namespace import SKOS
from prefixcommons.curie_util import contract_uri

from ontobio.ontol import Ontology, Synonym

# TODO: make configurable
GEMET = Namespace('http://www.eionet.europa.eu/gemet/2004/06/gemet-schema.rdf#')

class Skos(object):
    """
    SKOS is an RDF data model for representing thesauri and terminologies.

    See https://www.w3.org/TR/skos-primer/ for more details
    """

    def __init__(self, prefixmap=None, lang='en'):
        self.prefixmap = prefixmap if prefixmap is not None else {}
        self.lang = lang
        self.context = None

    def _uri2id(self, uri):
        s = "{:s}".format(str(uri))
        for prefix,uribase in self.prefixmap.items():
            if (s.startswith(uribase)):
                s = s.replace(uribase,prefix+":")
                return s
        curies = contract_uri(uri)
        if len(curies) > 0:
            return curies[0]
        return s

    def process_file(self,filename=None, format=None):
        """
        Parse a file into an ontology object, using rdflib
        """
        rdfgraph = rdflib.Graph()
        if format is None:
            if filename.endswith(".ttl"):
                format='turtle'
            elif filename.endswith(".rdf"):
                format='xml'
        rdfgraph.parse(filename, format=format)
        return self.process_rdfgraph(rdfgraph)
        
    def process_rdfgraph(self, rg, ont=None):
        """
        Transform a skos terminology expressed in an rdf graph into an Ontology object

        Arguments
        ---------
        rg: rdflib.Graph
            graph object

        Returns
        -------
        Ontology
        """
        # TODO: ontology metadata
        if ont is None:
            ont = Ontology()
            subjs = list(rg.subjects(RDF.type, SKOS.ConceptScheme))
            if len(subjs) == 0:
                logging.warning("No ConceptScheme")
            else:
                ont.id = self._uri2id(subjs[0])
            
        subset_map = {}
        for concept in rg.subjects(RDF.type, SKOS.Concept):
            for s in self._get_schemes(rg, concept):
                subset_map[self._uri2id(s)] = s
                
        for concept in sorted(list(rg.subjects(RDF.type, SKOS.Concept))):
            concept_uri = str(concept)
            id=self._uri2id(concept)
            logging.info("ADDING: {}".format(id))
            ont.add_node(id, self._get_label(rg,concept))
                    
            for defn in rg.objects(concept, SKOS.definition):
                if (defn.language == self.lang):
                    td = TextDefinition(id, escape_value(defn.value))
                    ont.add_text_definition(td)
                    
            for s in rg.objects(concept, SKOS.broader):
                ont.add_parent(id, self._uri2id(s))
                
            for s in rg.objects(concept, SKOS.related):
                ont.add_parent(id, self._uri2id(s), self._uri2id(SKOS.related))
                
            for m in rg.objects(concept, SKOS.exactMatch):
                ont.add_xref(id, self._uri2id(m))
                
            for m in rg.objects(concept, SKOS.altLabel):
                syn = Synonym(id, val=self._uri2id(m))
                ont.add_synonym(syn)
                
            for s in self._get_schemes(rg,concept):
                ont.add_to_subset(id, self._uri2id(s))
                
        return ont
    
    def _get_schemes(self, rg, concept):
        schemes = set(rg.objects(concept, SKOS.inScheme))
        schemes.update(rg.objects(concept, GEMET.group))
        return schemes
    
    def _get_label(self, rg,concept):
        labels = sorted(rg.preferredLabel(concept, lang=self.lang))
        if len(labels) == 0:
            return None
        if len(labels) > 1:
            logging.warning(">1 label for {} : {}".format(concept, labels))
        return labels[0][1].value
    
    
