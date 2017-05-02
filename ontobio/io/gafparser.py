"""
Parser for GAF and various TSVs
"""
import re
import requests
import tempfile
from contextlib import closing
import subprocess
import logging

class AssocParser():

    def pair_to_id(self, db, localid):
        return db + ":" + localid

    def _ensure_file(self, file):
        if isinstance(file,str):
            if file.startswith("ftp"):
                f = tempfile.NamedTemporaryFile()
                fn = f.name
                cmd = ['wget',file,'-O',fn]
                subprocess.run(cmd, check=True)
                return open(fn,"r")
            elif file.startswith("http") or file.startswith("ftp"):
                url = file
                with closing(requests.get(url, stream=False)) as resp:
                    logging.info("URL: {} STATUS: {} ".format(url, resp.status_code))
                    ok = resp.status_code == 200
                    if ok:
                        return io.StringIO(resp.text)
                    else:
                        return None
            else:
                 return open("myfile.txt", "r")
        else:
            return file
            
    def parse(self, file):
        file = self._ensure_file(file)
        assocs = []
        for line in file:
            if line.startswith("!"):
                continue
            assocs = assocs + self.parse_line(line)
        file.close()
        return assocs

    
    def parse_class_expression(self, x):
        ## E.g. exists_during(GO:0000753)
        ## Atomic class expressions only
        [(p,v)] = re.findall('(.*)\((.*)\)',x)
        return {
            'property':p,
            'filler':v
        }
        
    
class GpadParser(AssocParser):
    
    def skim(self, file):
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if len(vals) < 15:
                logging.error("Unexpected number of vals: {}".format(vals))
            rel = vals[2]
            # TODO: not
            id = self.pair_to_id(vals[0], vals[1])
            t = vals[3]
            tuples.append( (id,None,t) )
        return tuples

    def parse_line(self, line):            
        vals = line.split("\t")
        [db,
         db_object_id,
         relation,
         goid,
         reference,
         evidence,
         withfrom,
         foo,
         date,
         assigned_by,
         annotation_xp,
         gene_product_isoform] = vals
                
        id = self.pair_to_id(db, db_object_id)

        assocs = []
        xp_ors = annotation_xp.split("|")
        for xp_or in xp_ors:
            xp_ands = xp_or.split(",")
            extns = []
            for xp_and in xp_ands:
                if xp_and != "":
                    extns.append(self.parse_class_expression(xp_and))
            assoc = {
                'gafline': line,
                'subject': {
                    'id':id
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
    
class GafParser(AssocParser):
    
    def skim(self, file):
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if len(vals) < 15:
                logging.error("Unexpected number of vals: {}".format(vals))

            if vals[3] != "":
                continue
            id = self.pair_to_id(vals[0], vals[1])
            n = vals[2]
            t = vals[4]
            tuples.append( (id,n,t) )
        return tuples


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
    
## TODO - HPOA parser
