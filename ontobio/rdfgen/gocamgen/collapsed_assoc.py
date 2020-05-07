from typing import List
from ontobio.ontol_factory import OntologyFactory
from ontobio.io.gpadparser import GpadParser
from ontobio.io.assocparser import SplitLine

GPAD_PARSER = GpadParser()
BINDING_ROOT = "GO:0005488"  # binding
IPI_ECO_CODE = "ECO:0000353"


class CollapsedAssociationSet:
    def __init__(self, associations):
        self.associations = associations
        self.collapsed_associations = []
        self.assoc_dict = {}
        self.go_ontology = None

    def setup_ontologies(self):
        if self.go_ontology is None:
            self.go_ontology = OntologyFactory().create("go")

    def collapse_annotations(self):
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
        self.setup_ontologies()

        for a in self.associations:
            # Header
            subj_id = a["subject"]["id"]
            qualifiers = a["qualifiers"]
            term = a["object"]["id"]
            with_from = a["evidence"]["with_support_from"]
            eco_code = a["evidence"]["type"]
            extensions = get_annot_extensions(a)
            with_froms = get_with_froms(a)  # Handle pipe separation according to import requirements
            is_protein_binding = eco_code == IPI_ECO_CODE and BINDING_ROOT in self.go_ontology.ancestors(term, reflexive=True)
            if is_protein_binding:
                cas = self.find_or_create_collapsed_associations(subj_id, qualifiers, term, with_froms, extensions)
                with_from = None  # Don't use ontobio-parsed with_from on lines
            else:
                cas = [self.find_or_create_collapsed_association(subj_id, qualifiers, term, None, extensions)]
            for ca in cas:
                # Line
                association_line = CollapsedAssociationLine(a, with_from)
                ca.lines.append(association_line)

    def find_or_create_collapsed_association(self, subj_id, qualifiers, term, with_from, extensions):
        query_header = {
            'subject': {
                'id': subj_id
            },
            'qualifiers': sorted(qualifiers),
            'object': {
                'id': term
            },
            'object_extensions': extensions
        }
        if with_from:
            query_header['evidence'] = {'with_support_from': sorted(with_from)}
        for ca in self.collapsed_associations:
            if ca.header == query_header:
                return ca
        new_ca = CollapsedAssociation(query_header)
        self.collapsed_associations.append(new_ca)
        return new_ca

    def find_or_create_collapsed_associations(self, subj_id, qualifiers, term, with_froms, extensions):
        cas = []
        for wf in with_froms:
            ca = self.find_or_create_collapsed_association(subj_id, qualifiers, term, wf, extensions)
            cas.append(ca)
        return cas

    def __iter__(self):
        return iter(self.collapsed_associations)


class CollapsedAssociation:
    def __init__(self, header):
        self.header = header
        self.lines: List[CollapsedAssociationLine] = []

    def subject_id(self):
        if "subject" in self.header and "id" in self.header["subject"]:
            return self.header["subject"]["id"]

    def object_id(self):
        if "object" in self.header and "id" in self.header["object"]:
            return self.header["object"]["id"]

    def annot_extensions(self):
        if "object_extensions" in self.header:
            return self.header["object_extensions"].get("union_of")
        return {}

    def qualifiers(self):
        return self.header.get("qualifiers")

    def with_from(self):
        if "evidence" in self.header and "with_support_from" in self.header["evidence"]:
            return self.header["evidence"]["with_support_from"]

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
    def __init__(self, assoc, with_from=None):
        self.source_line = assoc["source_line"]
        self.references = sorted(assoc["evidence"]["has_supporting_reference"])
        self.evidence_code = assoc["evidence"]["type"]
        self.date = assoc["date"]
        self.assigned_by = assoc["provided_by"]
        self.annotation_properties = None
        self.with_from = with_from

        if "annotation_properties" in assoc:
            self.annotation_properties = assoc["annotation_properties"]

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


def get_annot_extensions(annot):
    if "object_extensions" in annot:
        return annot["object_extensions"]
    elif "extensions" in annot["object"]:
        return annot["object"]["extensions"]
    return {}


def get_with_froms(annot):
    source_line = annot["source_line"]
    vals = source_line.split("\t")
    with_from_col = vals[6]
    # Parse into array (by "|") of arrays (by ",")
    with_from_ds = []
    for piped_with_from in with_from_col.split("|"):
        # Will be bypassing ontobio ID validation? Let's try teaming up with ontobio functions!
        split_line = SplitLine(line=source_line, values=vals, taxon="")  # req'd for error reporting in ontobio?
        validated_comma_with_froms = GPAD_PARSER.validate_pipe_separated_ids(piped_with_from, split_line, empty_allowed=True, extra_delims=",")
        # comma_with_froms = piped_with_from.split(",")
        # validated_comma_with_froms = []
        # for wf in comma_with_froms:
        with_from_ds.append(validated_comma_with_froms)
    return with_from_ds


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


def extract_properties(annot):
    cols = annot["source_line"].rstrip().split("\t")
    if len(cols) >= 12:
        prop_col = cols[11]
        annot["annotation_properties"] = extract_properties_from_string(prop_col)
    return annot
