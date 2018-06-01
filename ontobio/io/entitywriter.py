"""
Classes for exporting entities.

So far only one implementation
"""
import re

def stringify(s):
    if s is None:
        return ""
    elif isinstance(s,list):
        return "|".join(s)
    else:
        return s

external_taxon = re.compile("taxon:([0-9]+)")
internal_taxon = re.compile("NCBITaxon:([0-9]+)")

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
    Writes entities in GPI format

    Takes an entity dictionary:
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
    def __init__(self, file=None):
        self.file = file

    def write_entity(self, entity):
        """
        Write a single entity to a line in the output file
        """
        db, db_object_id = self._split_prefix(entity)
        taxon = normalize_taxon(entity["taxon"]["id"])

        vals = [
            db,
            db_object_id,
            entity.get('label'),
            entity.get('full_name'),
            entity.get('synonyms'),
            entity.get('type'),
            taxon,
            entity.get('parents'),
            entity.get('xrefs'),
            entity.get('properties')
        ]

        self._write_row(vals)
