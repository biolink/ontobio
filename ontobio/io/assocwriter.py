class AssocWriterConfig():
    pass

class AssocWriter():
    def _split_prefix(self, ref):
        id = ref['id']
        [prefix, local_id] = id.split(':')
        return prefix, local_id

    def _write_row(self, vals):
        line = "\t".join(vals)
        self.file.write(line + "\n")

    def write(self, assocs):
        for a in assocs:
            self.write_assoc(a)
        
class GpadWriter(AssocWriter):

    def __init__(self, file=None):
        self.file = file

    def write_assoc(self, assoc):
        subj = assoc['subject']
        
        db, db_object_id = self._split_prefix(subj)

        rel = assoc['relation']
        qualifier = rel['id']
        if assoc['negated']:
            qualifier = 'NOT|' + qualifier

        goid = assoc['object']['id']

        ev = assoc['evidence']
        evidence = ev['type']
        withfrom = "|".join(ev['with_support_from'])
        reference = "|".join(ev['has_supporting_reference'])

        date = assoc['date']
        assigned_by = assoc['provided_by']

        annotation_xp = '' # TODO
        annotation_properties = '' # TODO
        interacting_taxon_id = '' ## TODO
        
        vals = [db,
                db_object_id,
                qualifier,
                goid,
                reference,
                evidence,
                withfrom,
                interacting_taxon_id, # TODO
                date,
                assigned_by,
                annotation_xp,
                annotation_properties]

        self._write_row(vals)
    
