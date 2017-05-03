"""
Parser for GAF and various Association TSVs
"""
import re
import requests
import tempfile
from contextlib import closing
import subprocess
import logging

class AssocParserConfig():
    """
    Configuration for parser
    """
    def __init__(self,
                 class_map=None,
                 entity_map=None,
                 taxa=None,
                 class_idspaces=None):
        self.class_map=class_map
        self.entity_map=entity_map
        self.taxa=taxa
        self.class_idspaces=class_idspaces

class Report():
    """
    A report object that is generated as a result of a parse
    """

    # Levels
    ERROR = 'ERROR'
    WARNING = 'WARNING'

    # Warnings: TODO link to gorules
    INVALID_ID = "Invalid identifier"
    
    def __init__(self):
        self.messages = []

    def error(self, line, type, obj):
        self.message(ERROR, line, type, obj)
    def message(self, level, line, type, obj):
        self.messages.add({'level':level,
                           'line':line,
                           'type':type,
                           'obj':obj})
        
class AssocParser():
    """
    Abstract superclass of all association parser classes
    """

    def parse(self, file):
        """
        Parse a file.

        File object may be http URLs, filename or `file-like-object`
        """
        file = self._ensure_file(file)
        assocs = []
        for line in file:
            if line.startswith("!"):
                continue
            line = line.strip("\n")
            assocs = assocs + self.parse_line(line)
        file.close()
        return assocs
    
    def _validate_id(self, id, line):
        if id.find(" ") > -1:
            self.report.error(line, Report.INVALID_ID, id)
    
    def _pair_to_id(self, db, localid):
        return db + ":" + localid

    def _taxon_id(self,id):
        return id.replace('taxon','NCBITaxon')
    
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
            
    
    def parse_class_expression(self, x):
        ## E.g. exists_during(GO:0000753)
        ## Atomic class expressions only
        [(p,v)] = re.findall('(.*)\((.*)\)',x)
        return {
            'property':p,
            'filler':v
        }
        
    
class GpadParser(AssocParser):
    """
    Parser for GO GPAD Format

    https://github.com/geneontology/go-annotation/blob/master/specs/gpad-gpi-1_2.md
    """

    def __init__(self,config=AssocParserConfig()):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        self.config = config
        self.report = Report()
        
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
            id = self._pair_to_id(vals[0], vals[1])
            t = vals[3]
            tuples.append( (id,None,t) )
        return tuples

    def parse_line(self, line):            
        """
        Parses a single line of a GPAD
        """
        vals = line.split("\t")
        [db,
         db_object_id,
         relation,
         goid,
         reference,
         evidence,
         withfrom,
         interacting_taxon_id, # TODO
         date,
         assigned_by,
         annotation_xp,
         annotation_properties] = vals
                
        id = self._pair_to_id(db, db_object_id)

        assocs = []
        xp_ors = annotation_xp.split("|")
        for xp_or in xp_ors:
            xp_ands = xp_or.split(",")
            extns = []
            for xp_and in xp_ands:
                if xp_and != "":
                    extns.append(self.parse_class_expression(xp_and))
            assoc = {
                'source_line': line,
                'subject': {
                    'id':id
                },
                'object': {
                    'id':goid,
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
    """
    Parser for GO GAF format
    """
    
    def __init__(self,config=AssocParserConfig()):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        self.config = config
        self.report = Report()
        
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
            id = self._pair_to_id(vals[0], vals[1])
            n = vals[2]
            t = vals[4]
            tuples.append( (id,n,t) )
        return tuples


    def parse_line(self, line, class_map=None, entity_map=None):
        """
        Parses a single line of a GAF
        """
        config = self.config
        
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

        id = self._pair_to_id(db, db_object_id)

        
        # Example use case: map2slim
        if config.class_map is not None:
            goid = self.map_id(goid, config.class_map)
            vals[4] = goid
            
        # Example use case: mapping from UniProtKB to MOD ID
        if config.entity_map is not None:
            id = self.map_id(id, config.entity_map)
            toks = id.split(":")
            db = toks[0]
            db_object_id = toks[1:]
            vals[1] = db_object_id

        # regenerate line post-mapping
        line = "\t".join(vals)

        taxa = [self._taxon_id(x) for x in taxon.split("|")]
        taxon = taxa[0]
        in_taxa = taxa[1:]
        
        synonyms = db_object_synonym.split("|")
        if db_object_synonym == "":
            synonyms = []
        

        assocs = []
        xp_ors = annotation_xp.split("|")
        for xp_or in xp_ors:
            xp_ands = xp_or.split(",")
            extns = []
            for xp_and in xp_ands:
                if xp_and != "":
                    extns.append(self.parse_class_expression(xp_and))

            relation = None
            qualifiers = qualifier.split("|")
            if qualifier == '':
                qualifiers = []
            negated =  'NOT' in qualifiers
            other_qualifiers = [q for q in qualifiers if q != 'NOT']
            if len(other_qualifiers) > 0:
                relation = other_qualifiers[0]
            else:
                if aspect == 'C':
                    relation = 'part_of'
                elif aspect == 'P':
                    relation = 'involved_in'
                elif aspect == 'F':
                    relation = 'enables'
                else:
                    relation = None
                    
            object = {'id':goid}
            if len(extns) > 0:
                object['extensions'] = extns
            if len(taxa) > 0:
                object['in_taxon'] = taxa

            subject = {
                'id':id,
                'label':db_object_symbol,
                'type': db_object_type,
                'fullname': db_object_name,
                'synonyms': synonyms,
                'taxon': {
                    'id': taxon
                }
            }
            subject_extns = []
            if gene_product_isoform is not None and gene_product_isoform != '':
                subject_extns.append({'property':'isoform', 'filler':gene_product_isoform})
            if len(subject_extns) > 0:
                subject['extensions'] = subject_extns

            evidence = {
                'type': evidence,
                'has_supporting_reference': reference
            }
            if withfrom != '':
                evidence['with_support_from'] = withfrom
            assoc = {
                'source_line': line,
                'subject': subject,
                'object': object,
                'negated': negated,
                'qualifiers': qualifiers,
                'relation': {
                    'id': relation
                },
                'evidence': evidence,
                'provided_by': assigned_by,
                'date': date,
                
            }
            assocs.append(assoc)
        return assocs
    
## TODO - HPOA parser
