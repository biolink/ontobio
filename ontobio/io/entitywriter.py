"""Classes for exporting entities."""
import re
from datetime import datetime

from ontobio.model.association import map_gp_type_label_to_curie

external_taxon = re.compile("taxon:([0-9]+)")
internal_taxon = re.compile("NCBITaxon:([0-9]+)")


def stringify(s):
    if s is None:
        return ""
    elif isinstance(s,list):
        return "|".join(s)
    else:
        return s


def normalize_taxon(taxon):
    global internal_taxon
    global external_taxon

    if external_taxon.match(taxon):
        # If we match here, then the internal view already exists and we're good
        return internal_taxon

    match = internal_taxon.match(taxon)
    if match:
        taxon_id = match.group(1)
        return "taxon:{num}".format(num=taxon_id)

    return taxon


class EntityWriter():
    """
    Abstract superclass of all association writer objects (Gpad, GAF)
    """

    # TODO: add to superclass
    def _split_prefix(self, ref):
        id = ref['id']
        [prefix, local_id] = id.split(':', maxsplit=1)
        return prefix, local_id

    # TODO: add to superclass
    def _write_row(self, vals):
        vals = [stringify(v) for v in vals]
        line = "\t".join(vals)
        self.file.write(line + "\n")

    # TODO: add to superclass
    def write_entity(self, e):
        """
        Write a single entity
        """
        pass  ## Implemented in subclasses

    def write(self, entities, meta=None):
        """
        Write a complete set of entities to a file

        Arguments
        ---------
        entities: list[dict]
            A list of entity dict objects
        meta: Meta
            metadata about association set (not yet implemented)

        """
        for e in entities:
            self.write_entity(e)


class GpiWriter(EntityWriter):
    """
    Writes entities in GPI 1.2 or 2.0 (https://github.com/geneontology/go-annotation/blob/master/specs/gpad-gpi-2-0.md) format

    :param file: file
    :param version: str

    Takes an "entity" dictionary generated typically from a GoAssociation object

    {
        'id': id, (String)
        'label': db_object_symbol, (String)
        'full_name': db_object_name, (String)
        'synonyms': synonyms, (List[str])
        'type': db_object_type, (String)
        'parents': parents, (List[Str])
        'xrefs': xref_ids, (List[Str])
        'taxon': {
            'id': self._taxon_id(taxon) (String)
        }
    }
    """
    def __init__(self, file=None, version=None):
        self.file = file
        self.version = version
        if self.file:
            if self.version == "2.0":
                self.file.write("!gpi-version: 2.0\n")
                self.file.write("!date-generated: " + datetime.now().strftime("%Y-%m-%dT%H:%M") + "\n")
                self.file.write("!generated-by: GOC\n")  # following conventions in assocwriter for now.
            else:
                self.file.write("!gpi-version: 1.2\n")
                self.file.write("!date-generated: " + datetime.now().strftime("%Y-%m-%dT%H:%M") + "\n")
                self.file.write("!generated-by: GOC\n")  # following conventions in assocwriter for now.

    def write_entity(self, entity):
        """
        Write a single entity to a line in the output file

        :param entity: dict ; typically a dictionary representing an instance of a GoAssociation object
        :param gpi_output_version: str ; the version of the GPAD output file to write
        :return: None

               GPI 2.0 spec <-- entity attributes
               
            1. DB_Object_ID <-- entity.id (CURIE format)
            2. DB_Object_symbol <-- entity.label
            3. DB_Object_Name <-- entity.full_name
            4. DB_Object_Synonyms <-- entity.synonyms
            5. DB_Object_Type <-- entity.type
            6. DB_Object_Taxon <-- entity.taxon
            7. Encoded_by <-- does not appear in GAF file, this is optional in GPI
            8. Parent_Protein <-- entity.parents # unclear if this is a list or a single value
            9. Protein_Containing_Complex_Members <-- does not appear in GAF file, this is optional in GPI
            10. DB_Xrefs <-- entity.xrefs
            11. Gene_Product_Properties <-- entity.properties

                GPI 1.2 spec <-- entity attributes

            1. DB <-- entity.id.prefix
            2. DB_Object_ID	 <-- entity.id.local_id
            3. DB_Object_Symbol <-- entity.label
            4. DB_Object_Name <-- entity.full_name
            5. DB_Object_Synonym(s) <-- entity.synonyms
            6. DB_Object_Type <-- entity.type
            7. Taxon <-- entity.taxon
            8. Parent_Object_ID <-- entity.parents # unclear if this is a list or a single value
            9. DB_Xref(s) <-- entity.xrefs
            10. Properties <-- entity.properties

        """

        taxon = entity.get("taxon").get("id")
        if normalize_taxon(taxon).startswith("taxon:"):
            taxon = taxon.replace("taxon:", "NCBITaxon:")

        if self.version == "2.0":
            vals = [
                entity.get('id'),  # DB_Object_ID
                entity.get('label'),  # DB_Object_symbol
                entity.get('full_name'),  # DB_Object_Name
                entity.get('synonyms'),  # DB_Object_Synonyms
                # GPI spec says this is single valued, GpiParser returns list, so take the first element here.
                str(map_gp_type_label_to_curie(entity.get('type')[0])),  # DB_Object_Type to curie vs. label
                taxon,  # DB_Object_Taxon, normalized to NCBITaxon prefix
                "",  # Encoded_by
                entity.get('parents'),  # Parent_Protein
                "",  # Protein_Containing_Complex_Members
                entity.get('xrefs'),  # DB_Xrefs
                entity.get('properties')  # Gene_Product_Properties
            ]
        else:
            prefix, local_id = self._split_prefix(entity)
            vals = [
                prefix,  # DB
                local_id,  # DB_Object_ID
                entity.get('label'),  # DB_Object_Symbol
                entity.get('full_name'),  # DB_Object_Full_Name
                entity.get('synonyms'),  # DB_Object_Synonyms
                entity.get('type'),  # DB_Object_Type
                normalize_taxon(entity.get("taxon").get("id")),  # taxon in gpi 1.2 was prefixed by `taxon:`
                entity.get('parents'),  # Parent_Object_ID
                entity.get('xrefs'),  # DB_Xref(s)
                entity.get('properties')  # Properties
            ]

        self._write_row(vals)
