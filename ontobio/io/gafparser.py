
class AssocParser():

    def pair_to_id(self, db, localid):
        return db + ":" + localid


class GafParser(AssocParser):
    
    def skim(self, file):
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if vals[3] != "":
                continue
            id = self.pair_to_id(vals[0], vals[1])
            n = vals[2]
            t = vals[4]
            tuples.append( (id,n,t) )
        return tuples

    def parse(self, file):
        assocs = []
        for line in file:
            if line.startswith("!"):
                continue
            assocs = assocs + self.parse_line(line)
        return assocs

    def parse_line(self, line):            
        vals = line.split("\t")
        if len(vals) == 15:
            vals = vals + ["",""]
        [db,
         db_object_id,
         db_object_symbol,
         qualifier,
         goid,
         reference,
         evidence,
         withfrom,
         aspect,
         db_object_name,
         db_object_synonym,
         db_object_type,
         taxon,
         date,
         assigned_by,
         annotation_xp,
         gene_product_isoform] = vals
        
        taxa = taxon.split("|")
        taxon = taxa[0] ## TODO

        synonyms = db_object_synonym.split("|")
        if db_object_synonym == "":
            synonyms = []
        
        id = self.pair_to_id(db, db_object_id)

        assocs = []
        xp_ors = annotation_xp.split("|")
        for xp_or in xp_ors:
            xp_ands = xp_or.split(",")
            extns = []
            for xp_and in xp_ands:
                if xp_and != "":
                    extns.append(self.parse_class_expression(xp_and))
            relation = qualifier
            assoc = {
                'gafline': line,
                'subject': {
                    'id':id,
                    'label':db_object_symbol,
                    'type': db_object_type,
                    'fullname': db_object_name,
                    'synonyms': synonyms,
                    'taxon': {
                        'id': taxon
                    }
                },
                'object': {
                    'id':id,
                    'extensions': extns
                },
                'relation': {
                    'id': relation
                },
                'evidence': {
                    'type': evidence,
                    'with_support_from': withfrom,
                    'has_supporting_reference': reference
                },
                'provided_by': assigned_by,
                'date': date,
                
            }
            assocs.append(assoc)
        return assocs
    
    def parse_class_expression(self, x):
        return None
