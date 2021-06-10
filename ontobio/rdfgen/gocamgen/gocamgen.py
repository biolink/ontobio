from ontobio.rdfgen.assoc_rdfgen import CamRdfTransform, TurtleRdfWriter, genid, prefix_context
from ontobio.rdfgen import relations
from ontobio.vocabulary.relations import OboRO, Evidence
from ontobio.vocabulary.upper import UpperLevel
from prefixcommons.curie_util import expand_uri, contract_uri
from rdflib.namespace import OWL, RDF
from rdflib import Literal
from rdflib.term import URIRef
from rdflib.namespace import Namespace
import rdflib
import datetime
import dateutil.parser
import os.path as path
import logging
from typing import List
from ontobio.rdfgen.gocamgen.triple_pattern_finder import TriplePattern, TriplePatternFinder
from ontobio.rdfgen.gocamgen.subgraphs import AnnotationSubgraph
from ontobio.rdfgen.gocamgen.utils import sort_terms_by_ontology_specificity, ShexHelper, GroupsHelper
from ontobio.rdfgen.gocamgen import errors, collapsed_assoc
from ontobio.model.association import GoAssociation, ExtensionUnit, ConjunctiveSet, ymd_str
from ontobio.io.assocparser import AssocParserConfig


# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel("INFO")

ro = OboRO()
evt = Evidence()
upt = UpperLevel()
LEGO = Namespace("http://geneontology.org/lego/")
LAYOUT = Namespace("http://geneontology.org/lego/hint/layout/")
PAV = Namespace('http://purl.org/pav/')
DC = Namespace("http://purl.org/dc/elements/1.1/")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
GOREL = Namespace("http://purl.obolibrary.org/obo/GOREL_")
NCBITAXON = Namespace("http://purl.obolibrary.org/obo/NCBITaxon_")
BIOLINK = Namespace("https://w3id.org/biolink/vocab/")

# Stealing a lot of code for this from ontobio.rdfgen:
# https://github.com/biolink/ontobio


def expand_uri_wrapper(id):
    c = prefix_context
    c['GOREL'] = "http://purl.obolibrary.org/obo/GOREL_"
    uri = expand_uri(id, cmaps=[c])
    return uri

def contract_uri_wrapper(id):
    uri = contract_uri(id, cmaps=[prefix_context])
    return uri

HAS_SUPPORTING_REFERENCE = URIRef(expand_uri_wrapper("dc:source"))
ENABLED_BY = URIRef(expand_uri_wrapper(ro.enabled_by))
ENABLES = URIRef(expand_uri_wrapper(ro.enables))
INVOLVED_IN = URIRef(expand_uri_wrapper(ro.involved_in))
PART_OF = URIRef(expand_uri_wrapper(ro.part_of))
OCCURS_IN = URIRef(expand_uri_wrapper(ro.occurs_in))
COLOCALIZES_WITH = URIRef(expand_uri_wrapper(ro.colocalizes_with))
CONTRIBUTES_TO = URIRef(expand_uri_wrapper("RO:0002326"))
MOLECULAR_FUNCTION = URIRef(expand_uri_wrapper(upt.molecular_function))
REGULATES = URIRef(expand_uri_wrapper("RO:0002211"))
LOCATED_IN = URIRef(expand_uri_wrapper("RO:0001025"))

# RO_ONTOLOGY = OntologyFactory().create("http://purl.obolibrary.org/obo/ro.owl")  # Need propertyChainAxioms to parse (https://github.com/biolink/ontobio/issues/312)
INPUT_RELATIONS = {
    #TODO Create rule for deciding (MOD-specific?) whether to convert has_direct_input to has input
    # "has_direct_input": "RO:0002400",
    "has_direct_input": "RO:0002233",
    "has input": "RO:0002233",
    "has_input": "RO:0002233",
    "occurs_in": "BFO:0000066",
    "has_agent": "RO:0002218"
}
ACTS_UPSTREAM_OF_RELATIONS = {
    "acts_upstream_of": "RO:0002263",
    "acts_upstream_of_or_within": "RO:0002264",
    "acts upstream of or within, positive effect": "RO:0004032",
    "acts upstream of or within, negative effect": "RO:0004033",
    "acts_upstream_of_positive_effect": "RO:0004034",
    "acts_upstream_of_negative_effect": "RO:0004035",
}
HAS_REGULATION_TARGET_RELATIONS = {
    # WB:WBGene00013591 involved_in GO:0042594
    "has_regulation_target": ""
}
REGULATES_CHAIN_RELATIONS = [
    "regulates_o_occurs_in",
    "regulates_o_acts_on_population_of"
]


SHEX_HELPER = ShexHelper()
GROUPS_HELPER = GroupsHelper()


def has_regulation_target_bucket(ontology, term):
    ancestors = ontology.ancestors(term, reflexive=True)
    buckets = []
    if "GO:0065009" in ancestors:
        buckets.append("a")
    if "GO:0010468" in ancestors:
        buckets.append("b")
    if "GO:0002092" in ancestors or "GO:0042176" in ancestors:
        buckets.append("c")
    if "GO:0019538" in ancestors or "GO:0032880" in ancestors:
        buckets.append("d")
    return buckets


now = datetime.datetime.now()


class Annoton():
    def __init__(self, subject_id, assocs, connections=None):
        self.enabled_by = subject_id
        self.annotations = assocs
        self.connections = connections
        self.individuals = {}


class GoCamEvidence:
    DEFAULT_CONTRIBUTOR = "http://orcid.org/0000-0002-6659-0416"
    DEFAULT_PROVIDED_BY = "http://geneontology.org"  # GO in groups.yaml

    def __init__(self, code, references, contributors=[], date="", comments=[], source_line="", with_from=None, provided_bys: List = []):
        self.evidence_code = code
        self.references = references
        self.date = date
        self.contributors = contributors
        self.provided_bys = provided_bys
        self.comments = comments
        self.source_line = source_line
        self.with_from = with_from
        self.id = None

    @staticmethod
    def create_from_annotation(annot: collapsed_assoc.CollapsedAssociationLine):
        source_line = annot.source_line.rstrip().replace("\t", " ")
        contributors = []
        if "contributor-id" in annot.annotation_properties:
            contributors = annot.annotation_properties["contributor-id"]
        if len(contributors) == 0:
            contributors = [GoCamEvidence.DEFAULT_CONTRIBUTOR]
        provided_by = GROUPS_HELPER.lookup_group_id(annot.assigned_by)  # Needs to be resolved to URI, e.g. ZFIN->http://zfin.org
        comments = []
        if "comment" in annot.annotation_properties:
            comments = annot.annotation_properties["comment"]

        return GoCamEvidence(annot.evidence_code, annot.references,
                           contributors=contributors,
                           # "{date}T{time}".format(date=ymd_str(date), time=date.time)
                           date=ymd_str(annot.date, separator="-"),
                           provided_bys=[provided_by],
                           comments=comments,
                           source_line=source_line)

    @staticmethod
    def create_from_collapsed_association(collapsed_association: collapsed_assoc.CollapsedAssociation):
        evidences = []
        for line in collapsed_association:
            evidence = GoCamEvidence.create_from_annotation(line)
            if line.with_from:
                evidence.with_from = ",".join(line.with_from)
            evidences.append(evidence)
        return evidences

    @staticmethod
    def max_date(evidences: List):
        all_dates = [e.date for e in evidences]
        mdate = sorted(all_dates, key=lambda x: dateutil.parser.parse(x), reverse=True)[0]
        return mdate


class GoCamModel:
    # TODO: Not using anymore maybe get rid of?
    relations_dict = {
        "has_direct_input": "RO:0002400",
        "has input": "RO:0002233",
        "has_regulation_target": "RO:0002211",  # regulates
        "regulates_activity_of": "RO:0002578",  # directly regulates
        "with_support_from": "RO:0002233",  # has input
        "directly_regulates": "RO:0002578",
        "directly_positively_regulates": "RO:0002629",
        "directly_negatively_regulates": "RO:0002630",
        "colocalizes_with": "RO:0002325",
        "contributes_to": "RO:0002326",
        "part_of": "BFO:0000050",
        "acts_upstream_of": "RO:0002263",
        "acts_upstream_of_negative_effect": "RO:0004035",
        "acts_upstream_of_or_within": "RO:0002264",
        "acts_upstream_of_positive_effect": "RO:0004034",
        "acts upstream of, negative effect": "RO:0004035",
        "acts_upstream_of_or_within_negative_effect": "RO:0004033",
        "acts_upstream_of_or_within_positive_effect": "RO:0004032",
        "located_in": "RO:0001025",
    }

    def __init__(self, modeltitle, connection_relations=None, store=None, model_id=None, modelstate=None):
        self.modeltitle = modeltitle
        cam_writer = CamTurtleRdfWriter(self.modeltitle, store=store, model_id=model_id)
        self.writer = AnnotonCamRdfTransform(cam_writer)
        self.classes = []
        self.individuals = {}   # Maintain entity-to-IRI dictionary. Prevents dup individuals but we may want dups?
        # TODO: Refactor to make graph more prominent
        self.graph = self.writer.writer.graph
        if connection_relations is None:
            self.connection_relations = GoCamModel.relations_dict
        else:
            self.connection_relations = connection_relations
        self.declare_properties()
        if modelstate is None:
            modelstate = "development"
        self.declare_modelstate(modelstate)

    def write(self, filename, format='ttl'):
        if path.splitext(filename)[1] != ".ttl":
            filename += ".ttl"
        with open(filename, 'wb') as f:
            self.writer.writer.serialize(destination=f, format=format)

    def declare_contributor(self, contributor: str):
        self.graph.add((self.writer.writer.base, DC.contributor, Literal(contributor)))

    def declare_provided_by(self, provided_by: str):
        self.graph.add((self.writer.writer.base, PAV.providedBy, Literal(provided_by)))

    def declare_modelstate(self, modelstate: str):
        self.graph.add((self.writer.writer.base, URIRef("http://geneontology.org/lego/modelstate"), Literal(modelstate)))

    def declare_properties(self):
        # AnnotionProperty
        self.writer.emit_type(URIRef("http://geneontology.org/lego/evidence"), OWL.AnnotationProperty)
        self.writer.emit_type(URIRef("http://geneontology.org/lego/hint/layout/x"), OWL.AnnotationProperty)
        self.writer.emit_type(URIRef("http://geneontology.org/lego/hint/layout/y"), OWL.AnnotationProperty)
        self.writer.emit_type(URIRef("http://purl.org/pav/providedBy"), OWL.AnnotationProperty)
        self.writer.emit_type(URIRef("http://purl.org/dc/elements/1.1/contributor"), OWL.AnnotationProperty)
        self.writer.emit_type(URIRef("http://purl.org/dc/elements/1.1/date"), OWL.AnnotationProperty)
        self.writer.emit_type(URIRef("http://purl.org/dc/elements/1.1/source"), OWL.AnnotationProperty)

    def declare_class(self, class_id):
        if class_id not in self.classes:
            self.writer.emit_type(URIRef(expand_uri_wrapper(class_id)), OWL.Class)
            self.classes.append(class_id)

    def declare_individual(self, entity_id, evidences: List[GoCamEvidence] = None, negated=False):
        entity = genid(base=self.writer.writer.base + '/')
        # TODO: Make this add_to_graph
        if negated:
            self.writer.emit_not(entity, self.writer.uri(entity_id))
        else:
            self.writer.emit_type(entity, self.writer.uri(entity_id))
        self.writer.emit_type(entity, OWL.NamedIndividual)
        if evidences:
            # Emit max date all contributors
            max_date = GoCamEvidence.max_date(evidences)
            self.writer.emit(entity, DC.date, Literal(max_date))
            all_contributors = set()
            all_provided_bys = set()
            for e in evidences:
                [all_contributors.add(c) for c in e.contributors]
                [all_provided_bys.add(pb) for pb in e.provided_bys]
            for c in all_contributors:
                self.writer.emit(entity, DC.contributor, Literal(c))
            for pb in all_provided_bys:
                self.writer.emit(entity, PAV.providedBy, Literal(pb))
        self.individuals[entity_id] = entity
        return entity

    def add_axiom(self, statement, evidence=None):
        (source_id, property_id, target_id) = statement
        stmt_id = self.find_bnode(statement)
        if stmt_id is None:
            stmt_id = self.writer.blanknode()
            self.writer.emit_type(stmt_id, OWL.Axiom)
        self.writer.emit(stmt_id, OWL.annotatedSource, source_id)
        self.writer.emit(stmt_id, OWL.annotatedProperty, property_id)
        self.writer.emit(stmt_id, OWL.annotatedTarget, target_id)
        self.writer.emit_type(property_id, OWL.ObjectProperty)

        if evidence:
            self.add_evidence(stmt_id, evidence.evidence_code, evidence.references)

        return stmt_id

    def create_axiom(self, subject_id, relation_uri, object_id):
        # If not URIRef, will be class IDs
        subject_uri = subject_id if isinstance(subject_id, URIRef) else self.declare_individual(subject_id)
        object_uri = object_id if isinstance(object_id, URIRef) else self.declare_individual(object_id)
        axiom_id = self.add_axiom(self.writer.emit(subject_uri, relation_uri, object_uri))
        return axiom_id

    # TODO: Explicitly type subject, object parameters. Are they Class ID URIs or instance URIs?
    # def find_or_create_axiom_by_class_id_uri
    # def find_or_create_axiom_by_instance_uri
    def find_or_create_axiom(self, subject_id : str, relation_uri : URIRef, object_id : str, annoton=None,
                             exact_length=False):
        # Maybe overkill but gonna try using find_pattern_recursive to find only one triple
        # TODO: Replace the TriplePattern stuff w/ SPARQL but need 'exact_length' to work
        pattern = TriplePattern([(subject_id, relation_uri, object_id)])
        found_triples = TriplePatternFinder().find_pattern_recursive(self, pattern, exact_length=True)
        # found_triples = self.triples_by_ids(subject_id, relation_uri, object_id)
        if len(found_triples) > 0:
            # Gonna be a list of "triple-chains", itself a list of triples, and each triple is sort like a 3-index list.
            # So we just want the first triple from the first chain:
            found_triple = found_triples[0][0]
            subject_uri = found_triple[0]
            object_uri = found_triple[2]
            axiom_id = self.find_bnode(found_triple)
        else:
            # subject_uri = self.declare_individual(subject_id)
            subject_uri = subject_id if isinstance(subject_id, URIRef) else self.declare_individual(subject_id)
            object_uri = object_id if isinstance(object_id, URIRef) else self.declare_individual(object_id)
            # TODO Can emit() be changed to emit_axiom()?
            axiom_id = self.add_axiom(self.writer.emit(subject_uri, relation_uri, object_uri))
        if annoton and relation_uri == ENABLED_BY:
            annoton.individuals[subject_id] = subject_uri
            annoton.individuals[object_id] = object_uri
        return axiom_id

    def add_evidence(self, axiom, evidence: GoCamEvidence, emit_date=True):
        # Try finding existing evidence object containing same type and references
        # ev_id = self.writer.find_or_create_evidence_id(ev)
        ev_id = self.writer.create_evidence(evidence)
        self.writer.emit(axiom, URIRef("http://geneontology.org/lego/evidence"), ev_id)
        ### Emit ev fields to axiom here TODO: Couple evidence and axiom emitting together
        self.writer.emit(axiom, RDFS.comment, Literal(evidence.source_line))
        for c in evidence.contributors:
            self.writer.emit(axiom, DC.contributor, Literal(c))
        for pb in evidence.provided_bys:
            self.writer.emit(axiom, PAV.providedBy, Literal(pb))
        if emit_date:
            self.writer.emit(axiom, DC.date, Literal(evidence.date))

    def add_evidences(self, axiom, evidences: List[GoCamEvidence]):
        for e in evidences:
            self.add_evidence(axiom, e, emit_date=False)
        max_date = GoCamEvidence.max_date(evidences)
        self.writer.emit(axiom, DC.date, Literal(max_date))

    def add_connection(self, gene_connection, source_annoton):
        # Switching from reusing existing activity node from annoton to creating new one for each connection -
        # Maybe SPARQL first to check if annoton activity already used for connection?
        # Check annoton for existing activity.
        # if gene_connection.object_id in source_annoton.individuals:
        #     # If exists and activity has connection relation,
        #     # Look for two triples: (gene_connection.object_id, ENABLED_BY, source_annoton.enabled_by) and
        #     (gene_connection.object_id, connection_relations, anything)
        # Annot MF should be declared by now - don't declare object_id if object_id == annot MF?
        if gene_connection.gp_b not in self.individuals:
            return
        source_id = None
        uri_list = self.uri_list_for_individual(gene_connection.object_id)
        for u in uri_list:
            if gene_connection.relation in self.connection_relations:
                rel = URIRef(expand_uri_wrapper(self.connection_relations[gene_connection.relation]))
                # Annot MF should be declared by now - don't declare object_id if object_id == annot MF?
                try:
                    annot_mf = source_annoton.molecular_function["object"]["id"]
                except:
                    annot_mf = ""
                if (u, rel, None) in self.writer.writer.graph and gene_connection.object_id != annot_mf:
                    source_id = self.declare_individual(gene_connection.object_id)
                    source_annoton.individuals[gene_connection.object_id] = source_id
                    break

        if source_id is None:
            try:
                source_id = source_annoton.individuals[gene_connection.object_id]
            except KeyError:
                source_id = self.declare_individual(gene_connection.object_id)
                source_annoton.individuals[gene_connection.object_id] = source_id
        # Add enabled by stmt for object_id - this is essentially adding another annoton
        # connecting gene-to-extension/with-MF to the model
        self.writer.emit(source_id, ENABLED_BY, source_annoton.individuals[source_annoton.enabled_by])
        self.writer.emit_axiom(source_id, ENABLED_BY, source_annoton.individuals[source_annoton.enabled_by])
        property_id = URIRef(expand_uri_wrapper(self.connection_relations[gene_connection.relation]))
        target_id = self.individuals[gene_connection.gp_b]
        # Annotate source MF GO term NamedIndividual with relation code-target MF term URI
        self.writer.emit(source_id, property_id, target_id)
        # Add axiom (Source=MF term URI, Property=relation code, Target=MF term URI)
        self.writer.emit_axiom(source_id, property_id, target_id)

    def uri_list_for_individual(self, individual):
        uri_list = []
        graph = self.writer.writer.graph
        for t in graph.triples((None,None,self.writer.uri(individual))):
            uri_list.append(t[0])
        return uri_list

    def triples_by_ids(self, subject, relation_uri, object_id):
        graph = self.writer.writer.graph

        triples = []
        if isinstance(subject, URIRef) or subject is None:
            subjects = [subject]
        else:
            subjects = self.uri_list_for_individual(subject)
        if isinstance(object_id, URIRef) or object_id is None:
            objects = [object_id]
        else:
            objects = self.uri_list_for_individual(object_id)
        for object_uri in objects:
            for subject_uri in subjects:
                # if (subject_uri, relation_uri, object_uri) in graph:
                #     triples.append((subject_uri, relation_uri, object_uri))
                for t in graph.triples((subject_uri, relation_uri, object_uri)):
                    triples.append(t)
        return triples

    def individual_label_for_uri(self, uri):
        ind_list = []
        graph = self.writer.writer.graph
        for t in graph.triples((uri, RDF.type, None)):
            if t[2] != OWL.NamedIndividual:  # We know OWL.NamedIndividual triple doesn't contain the label so don't return it
                ind_list.append(t[2])
        return ind_list

    def class_for_uri(self, uri):
        try:
            class_curie = contract_uri_wrapper(self.individual_label_for_uri(uri)[0])[0]
            return class_curie
        except:
            return None

    def axioms_for_source(self, source, property_uri=None):
        if property_uri is None:
            property_uri = OWL.annotatedSource
        axiom_list = []
        graph = self.writer.writer.graph
        for uri in self.uri_list_for_individual(source):
            for t in graph.triples((None, property_uri, uri)):
                axiom_list.append(t[0])
        return axiom_list

    def find_bnode(self, triple):
        (subject, predicate, object_id) = triple
        s_triples = self.writer.writer.graph.triples((None, OWL.annotatedSource, subject))
        s_bnodes = [s for s, p, o in s_triples]
        p_triples = self.writer.writer.graph.triples((None, OWL.annotatedProperty, predicate))
        p_bnodes = [s for s, p, o in p_triples]
        o_triples = self.writer.writer.graph.triples((None, OWL.annotatedTarget, object_id))
        o_bnodes = [s for s, p, o in o_triples]
        bnodes = set(s_bnodes) & set(p_bnodes) & set(o_bnodes)
        if len(bnodes) > 0:
            return list(bnodes)[0]

    def triples_involving_individual(self, ind_id, relation=None):
        # "involving" meaning individual (URI) is either subject or object
        graph = self.writer.writer.graph
        found_triples = list(graph.triples((ind_id, relation, None)))
        for t in graph.triples((None, relation, ind_id)):
            if t not in found_triples:
                found_triples.append(t)
        return found_triples


def relation_equals(rel_a, rel_b):
    if ":" not in str(rel_a):
        rel_a = contract_uri_wrapper(relations.lookup_label(rel_a))
    if ":" not in str(rel_b):
        rel_b = contract_uri_wrapper(relations.lookup_label(rel_b))[0]

    # Get to curie str to compare
    result = str(rel_a) == str(rel_b)
    return result


class AssocGoCamModel(GoCamModel):
    ENABLES_O_RELATION_LOOKUP = {}

    def __init__(self, modeltitle, assocs: List[GoAssociation], config: AssocParserConfig=None, connection_relations=None, store=None, gpi_entities=None, model_id=None, modelstate=None):
        GoCamModel.__init__(self, modeltitle, connection_relations, store, model_id=model_id, modelstate=modelstate)
        self.ontology = config.ontology
        self.associations = collapsed_assoc.CollapsedAssociationSet(ontology=self.ontology, gpi_entities=gpi_entities)
        self.associations.collapse_annotations(assocs)
        self.go_aspector = None  # TODO: Can I always grab aspect from ontology term DS
        self.default_contributor = "http://orcid.org/0000-0002-6659-0416"
        self.contributors = set()
        self.provided_bys = set()
        self.graph.bind("GOREL", GOREL)  # Because GOREL isn't in context.jsonld's
        self.gpi_entities = gpi_entities
        self.errors: List[errors.GocamgenException] = []
        ncbi_taxon = self.taxon_id_from_entity(str(assocs[0].subject.id))
        # Emit model-level in_taxon triple from ncbi_taxon
        if ncbi_taxon:
            # <https://w3id.org/biolink/vocab/in_taxon> <http://purl.obolibrary.org/obo/NCBITaxon_10090>
            self.graph.add((self.writer.writer.base, BIOLINK.in_taxon, URIRef(expand_uri_wrapper(ncbi_taxon))))
        self.graph.add((self.writer.writer.base, DC.title, Literal(modeltitle)))

    def taxon_id_from_entity(self, entity_id: str):
        if entity_id in self.gpi_entities:
            return self.gpi_entities[entity_id]["taxon"]["id"]
        return None

    def translate(self):

        for a in self.associations:

            term = str(a.object_id())

            # Add evidences tied to axiom_ids
            evidences = GoCamEvidence.create_from_collapsed_association(a)
            # Record all contributors at model level
            for e in evidences:
                for c in e.contributors:
                    self.contributors.add(c)
                for pb in e.provided_bys:
                    self.provided_bys.add(pb)

            annotation_extensions = a.annot_extensions()

            # Translate extension - maybe add function argument for custom translations?
            if not annotation_extensions:
                annot_subgraph = self.translate_primary_annotation(a)
                # For annots w/o extensions, this is where we write subgraph to model
                annot_subgraph.write_to_model(self, evidences)
            else:
                aspect = self.go_aspector.go_aspect(term)

                # TODO: Handle deduping in collapsed_assoc - need access to extensions_mapper.dedupe_extensions
                annotation_extensions = collapsed_assoc.dedupe_extensions(annotation_extensions)

                # Split on those multiple occurs_in(same NS) extensions
                # TODO: Cleanup/refactor this splitting into separate method
                extension_sets_to_remove = []
                for uo in annotation_extensions:
                    # Grab occurs_in's
                    # Make a new uo if situation found
                    occurs_in_exts: List[ExtensionUnit] = [ext for ext in uo.elements if relation_equals(ext.relation,
                                                                                                         "occurs_in")]
                    # onto_grouping = {
                    #     "CL": [{}, {}],
                    #     "EMAPA": [{}]
                    # }
                    onto_grouping = {}
                    for ext in occurs_in_exts:
                        ont_prefix = ext.term.namespace
                        if ont_prefix not in onto_grouping:
                            onto_grouping[ont_prefix] = []
                        onto_grouping[ont_prefix].append(ext)
                    for ont_prefix, exts in onto_grouping.items():
                        if len(exts) > 1:
                            if uo not in extension_sets_to_remove:
                                extension_sets_to_remove.append(uo)  # Remove original set when we're done splitting
                            for ext in exts:
                                # Create new 'intersection_of' list
                                new_exts_list = []
                                # Add ext to this new list if its prefix is not ont_prefix
                                for int_of_ext in uo.elements:
                                    if not relation_equals(int_of_ext.relation, "occurs_in") or int_of_ext.term.namespace != ont_prefix:
                                        # Add the extensions that don't currently concern us
                                        new_exts_list.append(int_of_ext)
                                # Then add occurs_in ext in current iteration
                                new_exts_list.append(ext)
                                annotation_extensions.append(ConjunctiveSet(elements=new_exts_list))
                # Remove original, un-split extension from list so it isn't translated
                [annotation_extensions.remove(ext_set) for ext_set in extension_sets_to_remove]

                for uo in annotation_extensions:
                    int_bits = []
                    for rel in uo.elements:
                        int_bits.append(str(rel))
                    ext_str = ",".join(int_bits)

                    annot_subgraph = self.translate_primary_annotation(a)

                    intersection_extensions: List[ExtensionUnit] = collapsed_assoc.dedupe_extensions(uo.elements)

                    # Nesting repeated extension relations (i.e. occurs_in, part_of)
                    ext_rels_to_nest = ['occurs_in', 'part_of']  # Switch to turn on/off extension nesting
                    for ertn in ext_rels_to_nest:
                        nest_exts = [ext for ext in intersection_extensions if relation_equals(ext.relation, ertn)]
                        if len(nest_exts) > 1:
                            # Sort by specific term to general term
                            sorted_nest_ext_terms = sort_terms_by_ontology_specificity(
                                [ne.term for ne in nest_exts])
                            # Translate
                            loc_subj_n = annot_subgraph.get_anchor()
                            for idx, ne_term in enumerate(sorted_nest_ext_terms):
                                # location_relation could be part_of, occurs_in, or located_in
                                # Figure out what types of classes these are
                                # Use case here is matching to ShEx shape class
                                subj_shape = SHEX_HELPER.shape_from_class(AnnotationSubgraph.node_class(loc_subj_n),
                                                                          self.go_aspector)
                                loc_obj_n = annot_subgraph.add_instance_of_class(ne_term)
                                obj_shape = SHEX_HELPER.shape_from_class(str(ne_term),
                                                                         self.go_aspector)
                                # location_relation = "BFO:0000050"  # part_of
                                location_relation = SHEX_HELPER.relation_lookup(subj_shape, obj_shape)
                                if idx == 0 and ertn == "occurs_in":
                                    location_relation = "BFO:0000066"  # occurs_in - because MF -> @<AnatomicalEntity> OR @<CellularComponent>
                                annot_subgraph.add_edge(loc_subj_n, location_relation, loc_obj_n)

                                loc_subj_n = loc_obj_n  # For next iteration
                            # Remove from intersection_extensions because this is now already translated
                            [intersection_extensions.remove(ext) for ext in nest_exts]
                    for rel in intersection_extensions:
                        ext_relation = relations.lookup_uri(expand_uri_wrapper(str(rel.relation)), default="")
                        if ext_relation == "":
                            # AttributeError: 'NoneType' object has no attribute 'replace'
                            error_msg = "Relation '{}' not found in relations lookup. Skipping annotation translation.".format(str(rel.relation))
                            self.errors.append(errors.GocamgenException(error_msg))
                            continue
                        ext_target = str(rel.term)
                        if ext_relation not in list(INPUT_RELATIONS.keys()) + list(HAS_REGULATION_TARGET_RELATIONS.keys()):
                            # No RO term yet. Try looking up in RO
                            relation_term = self.translate_relation_to_ro(ext_relation)
                            if relation_term:
                                # print("Ext relation {} auto-mapped to {} in {}".format(ext_relation,
                                # relation_term, a.subject_id()))
                                INPUT_RELATIONS[ext_relation] = relation_term
                        if ext_relation in INPUT_RELATIONS:
                            ext_target_n = annot_subgraph.add_instance_of_class(ext_target)
                            # Need to find what mf we're talking about
                            anchor_n = annot_subgraph.get_anchor()
                            annot_subgraph.add_edge(anchor_n, INPUT_RELATIONS[ext_relation], ext_target_n)
                        # elif ext_relation in REGULATES_CHAIN_RELATIONS:
                        elif ext_relation.startswith("regulates_o_"):
                            # Get target MF from primary term (BP) e.g. GO:0007346 regulates some mitotic cell cycle
                            regulates_rel, regulated_term = self.get_rel_and_term_in_logical_definitions(term)
                            if regulates_rel:
                                # Need to derive chained relation (e.g. "occurs_in") from this ext rel.
                                # Just replace("regulates_o_", "")?
                                chained_rel_label = ext_relation.replace("regulates_o_", "")
                                chained_rel = INPUT_RELATIONS.get(chained_rel_label)
                                if chained_rel is None:
                                    chained_rel = self.translate_relation_to_ro(chained_rel_label)
                                if chained_rel is None:
                                    # We have tried all we can for this poor thing. Skip translating this extension.
                                    continue
                                regulated_term_n = annot_subgraph.add_instance_of_class(regulated_term)
                                anchor_n = annot_subgraph.get_anchor()
                                annot_subgraph.add_edge(anchor_n, regulates_rel, regulated_term_n)
                                ext_target_n = annot_subgraph.add_instance_of_class(ext_target)
                                annot_subgraph.add_edge(regulated_term_n, chained_rel, ext_target_n)
                            else:
                                err_msg = "Couldn't get regulates relation from LD of: {}".format(term)
                                logger.warning(err_msg)
                                self.errors.append(collapsed_assoc.CollapsedAssocGocamgenException(err_msg, a))
                        elif ext_relation in HAS_REGULATION_TARGET_RELATIONS:
                            if aspect == 'P':
                                # For BP annotations, translate 'has regulation target' to 'has input'.
                                ext_target_n = annot_subgraph.add_instance_of_class(ext_target)
                                anchor_n = annot_subgraph.get_anchor()
                                annot_subgraph.add_edge(anchor_n, INPUT_RELATIONS['has_input'], ext_target_n)
                            else:
                                buckets = has_regulation_target_bucket(self.ontology, term)
                                if len(buckets) > 0:
                                    bucket = buckets[0]  # Or express all buckets?
                                    # Four buckets
                                    if bucket in ["a", "d"]:
                                        regulates_rel, regulated_mf = self.get_rel_and_term_in_logical_definitions(term)
                                        if regulates_rel and regulated_mf:
                                            # [GP-A]<-enabled_by-[root MF]-regulates->[molecular function Z]-enabled_by->[GP-B]
                                            ext_target_n = annot_subgraph.add_instance_of_class(ext_target)
                                            regulated_mf_n = annot_subgraph.add_instance_of_class(regulated_mf)
                                            annot_subgraph.add_edge(regulated_mf_n, ro.enabled_by, ext_target_n)
                                            anchor_n = annot_subgraph.get_anchor()
                                            annot_subgraph.add_edge(anchor_n, regulates_rel, regulated_mf_n)
                                            # TODO: Suppress/delete (GP-A)<-enabled_by-(root MF)-part_of->(term)
                                            #  aka involved_in_translated
                                            # Remove (anchor_uri, None, term)
                                            # Is this anchor_uri always going to the root_mf?
                                            # Will the term individual be used for anything else?
                                            #   Other comma-delimited extensions on same annotation?
                                            # has_during? occurs_in?
                                            # WB:WBGene00001173 GO:0051343 ['has_regulation_target', 'occurs_in'] ['a']
                                            # WB:WBGene00006652 GO:0045944 ['has_regulation_target', 'occurs_in'] ['b']
                                            # WB:WBGene00003639 GO:0036003 ['happens_during', 'has_regulation_target'] ['b']
                                            # Other comma-delimited extensions (e.g. happens_during, has_input) need this triple?
                                            # WB:WBGene00002335 GO:1902685 ['has_regulation_target', 'occurs_in'] ['d']
                                        else:
                                            logger.warning("Couldn't get regulates relation and/or regulated term from LD of: {}".format(term))
                                    elif bucket in ["b", "c"]:
                                        regulates_rel, regulated_term = self.get_rel_and_term_in_logical_definitions(term)
                                        if regulates_rel:
                                            # find 'Y subPropertyOf regulates_rel' in RO where Y will be `causally
                                            # upstream of` relation
                                            # Ex. GO:0045944 -> RO:0002213 -> RO:0002304
                                            # edges(RO:0002213) only returns subProperties. Need superProperties
                                            # Gettin super properties
                                            causally_upstream_relation = self.get_causally_upstream_relation(regulates_rel)
                                            # GP-A<-enabled_by-[root MF]-part_of->[regulation of Z]-has_input->GP-B,-causally
                                            # upstream of (positive/negative effect)->[root MF]-enabled_by->GP-B
                                            ext_target_n = annot_subgraph.add_instance_of_class(ext_target)
                                            anchor_n = annot_subgraph.get_anchor()  # TODO: Gotta find MF. MF no longer anchor if primary term is BP
                                            annot_subgraph.add_edge(anchor_n, INPUT_RELATIONS["has input"], ext_target_n)
                                            root_mf_b_n = annot_subgraph.add_instance_of_class(upt.molecular_function)
                                            annot_subgraph.add_edge(anchor_n, causally_upstream_relation, root_mf_b_n)
                                            annot_subgraph.add_edge(root_mf_b_n, ro.enabled_by, ext_target_n)
                                            # WB:WBGene00001574 GO:1903363 ['happens_during', 'has_regulation_target'] ['c', 'd']
                                        else:
                                            logger.warning("Couldn't get regulates relation from LD of: {}".format(term))
                    # For annots w/ extensions, this is where we write subgraph to model
                    annot_subgraph.write_to_model(self, evidences)
        # self.extensions_mapper.go_aspector.write_cache()

        if len(self.contributors) == 0 or self.contributors == set(self.default_contributor):
            contributors = set(self.default_contributor)
        elif self.default_contributor in self.contributors:
            contributors = self.contributors - set(self.default_contributor)
        else:
            contributors = self.contributors
        for c in contributors:
            self.declare_contributor(c)
        for pb in self.provided_bys:
            self.declare_provided_by(pb)

    def translate_primary_annotation(self, annotation: collapsed_assoc.CollapsedAssociation):
        gp_id = str(annotation.subject_id())
        term = str(annotation.object_id())
        annot_subgraph = AnnotationSubgraph()

        # TODO: qualifiers are coming through as relation terms now
        for q_term in annotation.qualifiers:
            if ":" in str(q_term):
                # It's a curie (nice!) but we're talking labels
                # q = self.ro_ontology.label(str(q_term)).replace(" ", "_")
                q = self.ontology.label(str(q_term)).replace(" ", "_")
            else:
                q = q_term
            if q == "enables":
                term_n = annot_subgraph.add_instance_of_class(term, is_anchor=True, negated=annotation.negated)
                enabled_by_n = annot_subgraph.add_instance_of_class(gp_id)
                annot_subgraph.add_edge(term_n, "RO:0002333", enabled_by_n)
            elif q == "involved_in":
                mf_n = annot_subgraph.add_instance_of_class(upt.molecular_function)
                enabled_by_n = annot_subgraph.add_instance_of_class(gp_id)
                # term_n = annot_subgraph.add_instance_of_class(term)
                term_n = annot_subgraph.add_instance_of_class(term, is_anchor=True, negated=annotation.negated)
                annot_subgraph.add_edge(mf_n, "RO:0002333", enabled_by_n)
                annot_subgraph.add_edge(mf_n, "BFO:0000050", term_n)
            elif q in ACTS_UPSTREAM_OF_RELATIONS:
                # Look for existing GP <- enabled_by [root MF] -> causally_upstream_of BP
                causally_relation = self.get_causally_upstream_relation(ACTS_UPSTREAM_OF_RELATIONS[q])
                # mf_n = annot_subgraph.add_instance_of_class(upt.molecular_function, is_anchor=True)
                mf_n = annot_subgraph.add_instance_of_class(upt.molecular_function)
                enabled_by_n = annot_subgraph.add_instance_of_class(gp_id)
                # term_n = annot_subgraph.add_instance_of_class(term)
                term_n = annot_subgraph.add_instance_of_class(term, is_anchor=True, negated=annotation.negated)
                annot_subgraph.add_edge(mf_n, "RO:0002333", enabled_by_n)
                annot_subgraph.add_edge(mf_n, causally_relation, term_n)
            else:
                # TODO: should check that existing axiom/triple isn't connected to anything else; length matches exactly
                enabled_by_n = annot_subgraph.add_instance_of_class(gp_id)
                term_n = annot_subgraph.add_instance_of_class(term, is_anchor=True, negated=annotation.negated)
                # annot_subgraph.add_edge(enabled_by_n, self.relations_dict[q], term_n)
                if q == "part_of" and SHEX_HELPER.shape_from_class(term, self.go_aspector) == "CellularComponent":
                    # Using shex_shape function should exclude AnatomicalEntity from getting located_in
                    q = "located_in"
                if q not in self.relations_dict:
                    relation = self.translate_relation_to_ro(q)
                else:
                    relation = self.relations_dict[q]
                annot_subgraph.add_edge(enabled_by_n, relation, term_n)

        with_froms = annotation.with_from()
        if with_froms:
            for wf in with_froms:
                wf_n = annot_subgraph.add_instance_of_class(wf)

                annot_subgraph.add_edge(annot_subgraph.get_anchor(), "RO:0002233", wf_n)
        return annot_subgraph

    def translate_relation_to_ro(self, relation_label):
        # Also check in GO_REL and use xref to RO
        # for n in self.ro_ontology.nodes():
        #     node_label = self.ro_ontology.label(n)
        for n in self.ontology.nodes():
            node_label = self.ontology.label(n)
            if node_label == relation_label.replace("_", " "):
                return n
        # # Is GOREL in go-lego?
        # for n in self.ontology.nodes():
        #     node_label = self.ontology.label(n)
            if node_label == relation_label:
                gorel_node = self.ontology.node(n)
                # What we want will likely be in xref:
                xrefs = gorel_node['meta'].get('xrefs')
                if xrefs and len(xrefs) > 0:
                    for xref in xrefs:
                        val = xref['val']
                        if val.startswith('RO') or val.startswith('BFO'):
                            # print("{} xref'd to {}".format(n, val))
                            return val
                    fallback_rel = xrefs[0]['val']  # default to the the first xref - usually GOREL
                    self.writer.emit_type(URIRef(expand_uri_wrapper(fallback_rel)), OWL.ObjectProperty)
                    self.writer.emit(URIRef(expand_uri_wrapper(fallback_rel)), RDFS.label, Literal(relation_label))
                    return fallback_rel
                # print(gorel_node)  # No such luck so far getting matches

    def get_restrictions(self, term):
        lds = self.ontology.logical_definitions(term)
        restrictions = []
        for ld in lds:
            for r in ld.restrictions:
                # if r[0] in self.ro_ontology.descendants("RO:0002211", reflexive=True):
                if r[0] in self.ontology.descendants("RO:0002211", reflexive=True):
                    restrictions.append(r)
        return restrictions

    def get_rel_and_term_in_logical_definitions(self, term):
        term_restrictions = self.get_restrictions(term)
        if len(term_restrictions) > 0:
            first_restriction = term_restrictions[0]
            regulates_rel = first_restriction[0]
            regulated_term = first_restriction[1]
            return regulates_rel, regulated_term
        else:
            return None, None

    def get_causally_upstream_relation(self, relation):
        regulates = "RO:0002211"
        causally_upstream_relations = []
        if relation == regulates or regulates in self.ontology.ancestors(relation):
            for p in self.ontology.parents(relation,
                                              relations=['subPropertyOf']):
                # For GO:0045944 this is grabbing both RO:0002304 and RO:0002211
                # Need specifically RO:0002304; how to specify?
                #   regulates_rel will only ever be regulates, positively regulates, or
                #   negatively regulates. If regulates in parents, grab other term
                if not p == regulates:
                    causally_upstream_relations.append(p)
        # input relations could have some unique logical difference (e.g. positively_regulates vs acts_upstream_of)
        else:
            if relation in self.ENABLES_O_RELATION_LOOKUP:
                return self.ENABLES_O_RELATION_LOOKUP[relation]
            else:
                property_chain_axioms = self.ontology.get_property_chain_axioms(relation)
                causally_upstream_relation = property_chain_axioms[0].chain_predicate_ids[1]
                self.ENABLES_O_RELATION_LOOKUP[relation] = causally_upstream_relation
                return causally_upstream_relation
        if len(causally_upstream_relations) > 0:
            return causally_upstream_relations[0]
        else:
            return None


class ReferencePreference:
    # List order in python should be persistent
    order_of_prefix_preference = [
        "PMID",
        "GO_REF",
        "DOI"
    ]

    @classmethod
    def pick(cls, references):
        for pfx in cls.order_of_prefix_preference:
            for ref in references:
                if ref.upper().startswith(pfx.upper()):
                    return ref
        return references[0]


class CamTurtleRdfWriter(TurtleRdfWriter):
    def __init__(self, modeltitle, store=None, model_id: str = None):
        base = "http://model.geneontology.org"
        if model_id is not None:
            self.base = URIRef(model_id, base=base)
        else:
            self.base = genid(base=base)
        if store is not None:
            graph = rdflib.Graph(identifier=self.base, store=store)
        else:
            graph = rdflib.Graph(identifier=self.base)
        self.graph = graph
        self.graph.bind("owl", OWL)
        self.graph.bind("obo", "http://purl.obolibrary.org/obo/")
        self.graph.bind("dc", DC)
        self.graph.bind("rdfs", RDFS)

        self.graph.add((self.base, RDF.type, OWL.Ontology))

        # Model attributes TODO: Should move outside init
        self.graph.add((self.base, DC.date, Literal(datetime.date.today().isoformat())))
        self.graph.add((self.base, DC.title, Literal(modeltitle)))
        self.graph.add((self.base, OWL.versionIRI, self.base))


class AnnotonCamRdfTransform(CamRdfTransform):
    def __init__(self, writer=None):
        CamRdfTransform.__init__(self, writer)
        self.annotons = []
        self.classes = []
        self.evidences = []
        self.ev_ids = []
        self.bp_id = None

    # TODO Remove "find" feature
    def find_or_create_evidence_id(self, evidence):
        for existing_evidence in self.evidences:
            if evidence.evidence_code == existing_evidence.evidence_code and set(evidence.references) == set(existing_evidence.references):
                if existing_evidence.id is None:
                    existing_evidence.id = genid(base=self.writer.base + '/')
                    self.ev_ids.append(existing_evidence.id)
                return existing_evidence.id
        return self.create_evidence(evidence)

    def create_evidence(self, evidence):
        # Use/figure out standard for creating URIs
        # Find minerva code to generate URI, add to Noctua doc
        ev_id = genid(base=self.writer.base + '/')
        evidence.id = ev_id
        # ev_cls = self.eco_class(self.uri(evidence.evidence_code))
        # ev_cls = self.eco_class(evidence.evidence_code) # This is already ECO:##### due to a GPAD being used
        ev_cls = self.uri(evidence.evidence_code)
        self.emit_type(ev_id, OWL.NamedIndividual)
        self.emit_type(ev_id, ev_cls)
        self.emit(ev_id, DC.date, Literal(evidence.date))
        if evidence.with_from:
            self.emit(ev_id, URIRef("http://geneontology.org/lego/evidence-with"), Literal(evidence.with_from))
        for c in evidence.contributors:
            self.emit(ev_id, DC.contributor, Literal(c))
        for pb in evidence.provided_bys:
            self.emit(ev_id, PAV.providedBy, Literal(pb))
        ref_to_emit = ReferencePreference.pick(evidence.references)
        o = Literal(ref_to_emit)  # Needs to go into Noctua like 'PMID:####' rather than full URL
        self.emit(ev_id, HAS_SUPPORTING_REFERENCE, o)
        for c in evidence.comments:
            self.emit(ev_id, RDFS.comment, Literal(c))
        self.evidences.append(evidence)
        return evidence.id

    # Use only for OWLAxioms
    # There are two of these methods. AnnotonCamRdfTransform.find_bnode and GoCamModel.find_bnode. Which one is used?
    def find_bnode(self, triple):
        (subject,predicate,object_id) = triple
        s_triples = self.writer.graph.triples((None, OWL.annotatedSource, subject))
        s_bnodes = [s for s,p,o in s_triples]
        p_triples = self.writer.graph.triples((None, OWL.annotatedProperty, predicate))
        p_bnodes = [s for s,p,o in p_triples]
        o_triples = self.writer.graph.triples((None, OWL.annotatedTarget, object_id))
        o_bnodes = [s for s,p,o in o_triples]
        bnodes = set(s_bnodes) & set(p_bnodes) & set(o_bnodes)
        if len(bnodes) > 0:
            return list(bnodes)[0]

    def emit_axiom(self, source_id, property_id, target_id):
        stmt_id = self.blanknode()
        self.emit_type(stmt_id, OWL.Axiom)
        self.emit(stmt_id, OWL.annotatedSource, source_id)
        self.emit(stmt_id, OWL.annotatedProperty, property_id)
        self.emit(stmt_id, OWL.annotatedTarget, target_id)
        return stmt_id

    def find_annotons(self, enabled_by, annotons_list=None):
        found_annotons = []
        if annotons_list is not None:
            annotons = annotons_list
        else:
            annotons = self.annotons
        for annoton in annotons:
            if annoton.enabled_by == enabled_by:
                found_annotons.append(annoton)
        return found_annotons

    def add_individual(self, individual_id, annoton):
        obj_uri = self.uri(individual_id)
        if individual_id not in annoton.individuals:
            tgt_id = genid(base=self.writer.base + '/')
            annoton.individuals[individual_id] = tgt_id
            self.emit_type(tgt_id, obj_uri)
            self.emit_type(tgt_id, OWL.NamedIndividual)
        else:
            tgt_id = annoton.individuals[individual_id]
