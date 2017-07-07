from prefixcommons.curie_util import contract_uri, expand_uri, get_prefixes
from ontobio.vocabulary.relations import OboRO, Evidence
from ontobio.vocabulary.upper import UpperLevel
from ontobio.ecomap import EcoMap
from rdflib import Namespace
from rdflib import BNode
from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import RDF
from rdflib.namespace import RDFS
from rdflib.namespace import OWL
import rdflib
import logging
import uuid

ro = OboRO()
evt = Evidence()
upt = UpperLevel()

HAS_SUPPORTING_REFERENCE = URIRef(expand_uri(evt.has_supporting_reference, cmaps=[evt._prefixmap]))

ENABLED_BY = URIRef(expand_uri(ro.enabled_by))
ENABLES = URIRef(expand_uri(ro.enables))
INVOLVED_IN = URIRef(expand_uri(ro.involved_in))
PART_OF = URIRef(expand_uri(ro.part_of))
OCCURS_IN = URIRef(expand_uri(ro.occurs_in))
COLOCALIZES_WITH = URIRef(expand_uri(ro.colocalizes_with))
MOLECULAR_FUNCTION = URIRef(expand_uri(upt.molecular_function))


class RdfWriter(object):
    """
    Abstract base class for all RdfWriters
    """
    pass

class TurtleRdfWriter(RdfWriter):
    """
    Default implementation of RdfWriter

    use rdflib to generate a turtle file
    """
    def __init__(self):
        self.graph = rdflib.Graph()

    def add(self, s,p,o):
        self.graph.add((s,p,o))

    def serialize(self, destination=None, format='xml', **args):
        self.graph.serialize(destination, format, **args)


        
class RdfTransform(object):
    """
    base class for all RDF generators
    """

    def __init__(self, writer=None):
        if writer is None:
            writer = TurtleRdfWriter()
        self.writer = writer
        self.include_subject_info = False
        self.ecomap = EcoMap()
        self._emit_header_done = False
        self.uribase = 'http://example.org/'

    def genid(self):
        return URIRef(uuid.uuid4().urn)

    def blanknode(self):
        return BNode()
        
    def uri(self,id):
        # allow either atoms or objects
        if isinstance(id,dict):
            return self.uri(id['id'])
        logging.info("Expand: {}".format(id))
        return URIRef(expand_uri(id))
    
    def emit(self,s,p,o):
        logging.debug("TRIPLE: {} {} {}".format(s,p,o))
        self.writer.add(s,p,o)
        return (s,p,o)
    
    def emit_type(self,s,t):
        return self.emit(s,RDF.type,t)
    def emit_label(self,s,t):
        return self.emit(s,RDFS.label,o)

    def eco_class(self, code, coderef=None):
        eco_cls_id = self.ecomap.coderef_to_ecoclass(code, coderef)
        logging.debug(self.ecomap._mappings)
        logging.debug('ECO: {},{}->{}'.format(code, coderef, eco_cls_id))
        return self.uri(eco_cls_id)
    
    def translate_evidence(self, association, stmt):
        """

        ``
        _:1 a Axiom
            subject s
            predicate p
            object o
            evidence [ a ECO ; ...]
        ``
        
        """
        ev = association['evidence']
        ev_id = None
        if 'id' in ev:
            ev_id = self.uri(ev['id'])
        else:
            ev_id = self.genid()

        stmt_id = self.blanknode() ## OWL reification: must be blank
        (s,p,o) = stmt
        self.emit_type(stmt_id, OWL.Axiom)
        
        self.emit(stmt_id, OWL.subject, s)        
        self.emit(stmt_id, OWL.predicate, p)        
        self.emit(stmt_id, OWL.object, o)
        
        self.emit(stmt_id, self.uri(evt.axiom_has_evidence), ev_id)

        ev_cls = self.eco_class(self.uri(ev['type']))
        self.emit_type(ev_id, OWL.NamedIndividual)
        self.emit_type(ev_id, ev_cls)
        if 'with_support_from' in ev:
            for w in ev['with_support_from']:
                self.emit(ev_id, self.uri(evt.evidence_with_support_from), self.uri(w))
        for ref in ev['has_supporting_reference']:
            self.emit(ev_id, HAS_SUPPORTING_REFERENCE, self.uri(ref))
        if 'with_support_from' in ev:
            for ref in ev['with_support_from']:
                self.emit(ev_id, self.uri(evt.evidence_with_support_from), self.uri(ref))
        

class CamRdfTransform(RdfTransform):
    """
    Granular instance-based representation (GO-CAM)

    Perform gappy translation from simple assocs model to GOCAM

    See https://github.com/geneontology/minerva/blob/master/specs/owl-model.md
    """

    def emit_header(self):
        if self._emit_header_done:
            return
        self._emit_header_done = True
        self.emit_type(ENABLED_BY, OWL.ObjectProperty)
        self.emit_type(PART_OF, OWL.ObjectProperty)
        self.emit_type(OCCURS_IN, OWL.ObjectProperty)
    
    def translate(self, association):
        sub = association['subject']
        obj = association['object']
        rel = association['relation']
        sub_uri = self.uri(sub)
        obj_uri = self.uri(obj)

        # E.g. instance of gene product class
        enabler_id = self.genid()
        self.emit_type(enabler_id, sub_uri)
        self.emit_type(enabler_id, OWL.NamedIndividual)
        
        # E.g. instance of GO class
        tgt_id = self.genid()
        self.emit_type(tgt_id, obj_uri)
        self.emit_type(tgt_id, OWL.NamedIndividual)
        
        aspect = association['aspect']
        stmt = None

        # todo: use relation
        if aspect == 'F':
            stmt = self.emit(tgt_id, ENABLED_BY, enabler_id)
        elif aspect == 'P':
            mf_id = self.genid()
            self.emit_type(mf_id, MOLECULAR_FUNCTION)
            stmt = self.emit(mf_id, ENABLED_BY, enabler_id)
            stmt = self.emit(mf_id, PART_OF, tgt_id)
        elif aspect == 'C':
            mf_id = self.genid()
            self.emit_type(mf_id, MOLECULAR_FUNCTION)
            stmt = self.emit(mf_id, ENABLED_BY, enabler_id)
            stmt = self.emit(mf_id, OCCURS_IN, tgt_id)

        if self.include_subject_info:
            pass
            # TODO
        # TODO: extensions
        self.translate_evidence(association, stmt)
        
class SimpleAssocRdfTransform(RdfTransform):
    """
    Follows simple OBAN-style model

    See: https://github.com/EBISPOT/OBAN

    See also: https://github.com/monarch-initiative/dipper/
    """

    def emit_header(self):
        if self._emit_header_done:
            return
        self._emit_header_done = True
        
    def translate(self, association):
        sub = association['subject']
        obj = association['subject']
        rel = association['relation']['id']
        sub_uri = self.uri(sub)
        obj_uri = self.uri(obj)

        rel_url = None
        if rel == 'part_of':
            rel_uri = PART_OF
        elif rel == 'enables':
            rel_uri = ENABLES
        elif rel == 'involved_in':
            rel_uri = INVOLVED_IN
        elif rel == 'colocalizes_with':
            rel_uri = COLOCALIZES_WITH
        else:
            logging.error("Unknown: {}".format(rel))
            
        # TODO: extensions
        stmt = self.emit(sub_uri,rel_uri,obj_uri)

        # optionally include info about subject (e.g. gene)
        if self.include_subject_info:
            self.emit_label(sub_uri, sub)
            if 'taxon' in sub:
                taxon = sub['taxon']
                self.emit(sub_uri, ro.in_taxon, self.uri(taxon))
            # TODO syns etc

        self.translate_evidence(association, stmt)
        
