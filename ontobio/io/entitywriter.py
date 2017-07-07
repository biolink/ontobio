"""
Classes for exporting entities.

So far only one implementation
"""

def stringify(s):
    if s is None:
        return ""
    elif isinstance(s,list):
        return "|".join(s)
    else:
        return s

class EntityWriter():
    """
    Abstract superclass of all association writer objects (Gpad, GAF)
    """

    # TODO: add to superclass
    def _split_prefix(self, ref):
        id = ref['id']
        [prefix, local_id] = id.split(':')
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
    """
    def __init__(self, file=None):
        self.file = file

    def write_entity(self, entity):
        """
        Write a single association to a line in the output file
        """
        db, db_object_id = self._split_prefix(id)

        vals = [db,
                db_object_id,
                entity.get('label'),
                entity.get('full_name'),
                entity.get('synonyms'),
                entity.get('type'),
                entity.get('taxon')['id'],
                entity.get('parents'),
                entity.get('xrefs'),
                entity.get('properties')]

        self._write_row(vals)
    
