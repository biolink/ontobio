import logging
from typing import List
from ontobio.io.gpadparser import GpadParser
from ontobio.model.association import GoAssociation
from ontobio.rdfgen.gocamgen import errors

logger = logging.getLogger(__name__)

GPAD_PARSER = GpadParser()
BINDING_ROOT = "GO:0005488"  # binding
IPI_ECO_CODE = "ECO:0000353"


class GoAssocWithFrom:
    """
    Separate with/from column values into
    header vs line arrangement.
    Used for explicit placement in
    annotation assertions.
    """
    def __init__(self, header=None, line=None):
        if header is None:
            header = []
        if line is None:
            line = []
        self.header = sorted(header)
        self.line = sorted(line)

    def add_to_header(self, entity):
        self.header.append(entity)

    def add_to_line(self, entity):
        self.line.append(entity)

    def __str__(self):
        return f"Header: {','.join(self.header)} - Line: {','.join(self.line)}"


class CollapsedAssociationSet:
    def __init__(self, ontology, gpi_entities):
        self.collapsed_associations = []
        self.assoc_dict = {}
        self.go_ontology = ontology
        self.gpi_entities = gpi_entities

    def collapse_annotations(self, associations: List[GoAssociation]):
        # Here we shall decide the distinct assertion instances going into the model
        # This will reduce/eliminate need to SPARQL model graph
        # Group by:
        # 		1. ID
        # 		2. qualifiers (normalize order; any array gotta do this)
        # 		3. primary term
        # 		4. With/From (if primary term is BINDING_ROOT or descendant)
        # 		5. Extensions
        # 	Collapse multiple:
        # 		1. Reference
        # 		2. Evidence Code
        #       3. With/From (if primary term is not BINDING_ROOT or descendant)
        # 		4. Source line
        # 		5. Date
        # 		6. Assigned by
        # 		7. Properties
        for a in associations:
            separated_with_froms: List[GoAssocWithFrom] = self.get_with_froms(a)
            cas = []
            for wf in separated_with_froms:
                ca = self.find_or_create_collapsed_association(a, wf)
                association_line = CollapsedAssociationLine(a, wf.line)
                ca.lines.append(association_line)
                cas.append(ca)

    def find_or_create_collapsed_association(self, association: GoAssociation, with_from: GoAssocWithFrom):
        ca = self.find_by_go_association(association, with_from)
        if ca:
            return ca
        else:
            ca = CollapsedAssociation(association, with_from)
            self.collapsed_associations.append(ca)
            return ca

    def find_by_go_association(self, association: GoAssociation, with_from: GoAssocWithFrom):
        for ca in self.collapsed_associations:
            if ca.header_data_matches(association, with_from):
                return ca

    def __iter__(self):
        return iter(self.collapsed_associations)

    def get_with_froms(self, annot: GoAssociation) -> List[GoAssocWithFrom]:
        # The craziest example:
        # MGI:1  GO:0005515  IPI  PR:1,PR:2|WEIRD:1,PR:3|MGI:2
        with_from_ds = annot.evidence.with_support_from

        # Now arrange these into "header" and "line" values
        eco_code = str(annot.evidence.type)
        term = str(annot.object.id)
        is_binding = eco_code == IPI_ECO_CODE and BINDING_ROOT in self.go_ontology.ancestors(term, reflexive=True)
        if is_binding:
            # Using GPI, check with_froms for taxon equivalency to subj_id
            if self.gpi_entities:
                subject_id = str(annot.subject.id)
                if subject_id in self.gpi_entities:
                     subject_entity = self.gpi_entities[subject_id]
                else:
                    error_message = "Annotation Object ID '{}' missing from provided GPI. Skipping annotation translation.".format(subject_id)
                    logger.warning(error_message)
                    # Throw Exception and except-skip in model builder
                    raise errors.GocamgenException(error_message)

                values_separated: List[GoAssocWithFrom] = []
                for wf in with_from_ds:
                    wf_separated = GoAssocWithFrom()
                    for wf_id in wf.elements:
                        wf_id_str = str(wf_id)
                        wf_entity = self.gpi_entities.get(wf_id_str)
                        if wf_entity and wf_entity.get("taxon") == subject_entity["taxon"]:
                            wf_separated.add_to_header(wf_id_str)
                        wf_separated.add_to_line(wf_id_str)
                    values_separated.append(wf_separated)
            else:
                # Everything is defaulted to header if no GPI available
                values_separated = [GoAssocWithFrom(header=[str(ele) for ele in wf.elements]) for wf in with_from_ds]
                # values_separated = [GoAssocWithFrom(line=[str(ele) for ele in wf.elements]) for wf in with_from_ds]
        else:
            # Everything is defaulted to line if not binding
            values_separated = [GoAssocWithFrom(line=[str(ele) for ele in wf.elements]) for wf in with_from_ds]
        if len(values_separated) == 0:
            # Return empty object if with/from is blank
            values_separated = [GoAssocWithFrom()]
        return values_separated


class CollapsedAssociation:
    def __init__(self, association: GoAssociation, with_from: GoAssocWithFrom):
        self.subject = association.subject
        self.object = association.object
        self.negated = association.negated
        self.qualifiers = sorted(association.qualifiers, key=lambda q: str(q))
        self.with_froms = sorted(with_from.header)
        self.object_extensions = association.object_extensions
        self.lines: List[CollapsedAssociationLine] = []

    def header_data_matches(self, association: GoAssociation, with_from: GoAssocWithFrom):
        if self.subject_id() == str(association.subject.id) and \
           self.object_id() == str(association.object.id) and \
           self.negated == association.negated and \
           self.qualifiers == sorted(association.qualifiers, key=lambda q: str(q)) and \
           self.object_extensions == association.object_extensions and \
           self.with_froms == sorted(with_from.header):
            return True
        return False

    def subject_id(self):
        return str(self.subject.id)

    def object_id(self):
        return str(self.object.id)

    def annot_extensions(self):
        return self.object_extensions

    def with_from(self):
        return self.with_froms

    def __str__(self):
        # TODO: Reconstruct GPAD format or original line - could mean multiple lines for each evidence
        return "{} - {}".format(self.subject_id(), self.object_id())

    def __iter__(self):
        return iter(self.lines)


def dedupe_extensions(extensions):
    new_extensions = []
    for i in extensions:
        if i not in new_extensions:
            new_extensions.append(i)
    return new_extensions


class CollapsedAssociationLine:
    def __init__(self, assoc: GoAssociation, with_from=None):
        self.source_line = assoc.source_line
        self.references = [str(ref) for ref in sorted(assoc.evidence.has_supporting_reference, key=lambda x: str(x))]
        self.evidence_code = str(assoc.evidence.type)
        self.date = assoc.date
        self.assigned_by = assoc.provided_by
        self.with_from = with_from
        self.annotation_properties = extract_properties(assoc)

    def as_dict(self):
        ds = {
            "source_line": self.source_line,
            "evidence": {
                "type": self.evidence_code,
                "has_supporting_reference": self.references
            },
            "date": self.date,
            "provided_by": self.assigned_by,
        }
        if self.annotation_properties:
            ds["annotation_properties"] = self.annotation_properties
        if self.with_from:
            ds["evidence"]["with_support_from"] = self.with_from
        return ds


class CollapsedAssocGocamgenException(errors.GocamgenException):
    def __init__(self, message: str, assoc: CollapsedAssociation):
        self.message = message
        self.assoc = assoc

    def __str__(self):
        return "{}\n{}".format(self.message, "\n".join([l.source_line for l in self.assoc.lines]))


def get_annot_extensions(annot: GoAssociation):
    return annot.object_extensions


def extract_properties_from_string(prop_col):
    props = prop_col.split("|")
    props_dict = {}
    for p in props:
        k, v = p.split("=")
        if k in props_dict:
            props_dict[k].append(v)
        else:
            props_dict[k] = [v]
    return props_dict


def extract_properties(annot: GoAssociation):
    annotation_properties = {}
    property_keys = set([prop[0] for prop in annot.properties])
    for pk in property_keys:
        annotation_properties[pk] = annot.annotation_property_values(pk)
    return annotation_properties
