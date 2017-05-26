from marshmallow import Schema, fields, pprint

class NamedObjectSchema(Schema):
    id = fields.Str(readOnly=True, description='ID or CURIE e.g. MGI:1201606')
    label = fields.Str(readOnly=True, description='RDFS Label')
    description = fields.Str(readOnly=True, description='Descriptive text for the entity. For ontology classes, this will be a definition.')
    categories = fields.List(fields.String(readOnly=True, description='Type of object (inferred)'))
    types = fields.List(fields.String(readOnly=True, description='Type of object (direct)'))
    synonyms = fields.List(fields.Nested(SynonymPropertyValueSchema), description='list of synonyms or alternate labels')
    deprecated = fields.Boolean(description='True if the node is deprecated/obsoleted.')
    replaced_by = fields.List(fields.String(readOnly=True, description='Direct 1:1 replacement (if named object is obsoleted)'))
    consider = fields.List(fields.String(readOnly=True, description='Potential replacement object (if named object is obsoleted)'))

class EntityReferenceSchema(Schema):
    id = fields.Str(readOnly=True, description='ID or CURIE e.g. MGI:1201606')
    label = fields.Str(readOnly=True, description='RDFS Label')
    categories = fields.List(fields.String(readOnly=True, description='Type of object'))

class RelationSchema(NamedObjectSchema):
    pass

class PublicationSchema(NamedObjectSchema):
    pass

class TaxonSchema(Schema):
    id = fields.Str(readOnly=True, description='CURIE ID, e.g. NCBITaxon:9606')
    label = fields.Str(readOnly=True, description='RDFS Label')

class BioObjectSchema(NamedObjectSchema):
    taxon = fields.Nested(TaxonSchema, description='Taxon to which the object belongs')
    xrefs = fields.List(fields.String, description='Database cross-references. These are usually CURIEs, but may also be URLs. E.g. ENSEMBL:ENSG00000099940 ')

class AnnotationExtensionSchema(Schema):
    relation_chain = fields.List(fields.Nested(RelationSchema), description='Relationship type. If more than one value, interpreted as chain')
    filler = fields.Nested(NamedObjectSchema, description='Extension interpreted as OWL expression (r1 some r2 some .. some filler).')

class AssociationSchema(Schema):
    id = fields.Str(readOnly=True, description='Association/annotation unique ID')
    type = fields.Str(readOnly=True, description='Type of association, e.g. gene-phenotype')
    subject = fields.Nested(BioObjectSchema, description='Subject of association (what it is about), e.g. ClinVar:nnn, MGI:1201606')
    subject_extension = fields.List(fields.Nested(AnnotationExtensionSchema, description='Additional properties of the subject in the context of this association.'))
    object = fields.Nested(BioObjectSchema, description='Object (sensu RDF), aka target, e.g. HP:0000448, MP:0002109, DOID:14330')
    object_extension = fields.List(fields.Nested(AnnotationExtensionSchema, description='Additional properties of the object in the context of this association. See http://www.biomedcentral.com/1471-2105/15/155'))
    relation = fields.Nested(RelationSchema, description='Relationship type connecting subject and object')
    qualifiers = fields.List(fields.Nested(AssociationPropertyValueSchema, description='Qualifier on the association'))
    evidence_types = fields.List(fields.Nested(NamedObjectSchema), description='Evidence types (ECO classes) extracted from evidence graph')
    provided_by = fields.List(fields.String, description='Provider of association, e.g. Orphanet, ClinVar')
    publications = fields.List(fields.Nested(PublicationSchema), description='Publications supporting association, extracted from evidence graph')
