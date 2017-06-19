"""
Parsers for GAF and various Association TSVs.

All parser objects instantiate a subclass of the abstract `AssocParser` object

"""

# TODO: Refactor - move some stuff out into generic parser object

import re
import requests
import tempfile
from contextlib import closing
import subprocess
import logging
import io

TAXON = 'TAXON'
ENTITY = 'ENTITY'
ANNOTATION = 'ANNOTATION'


class AssocParserConfig():
    """
    Configuration for an association parser
    """
    def __init__(self,
                 remove_double_prefixes=False,
                 ontology=None,
                 repair_obsoletes=True,
                 entity_map=None,
                 valid_taxa=None,
                 class_idspaces=None,
                 entity_idspaces=None,
                 exclude_relations=[],
                 include_relations=[],
                 filter_out_evidence=[]):
        self.remove_double_prefixes=remove_double_prefixes
        self.ontology=ontology
        self.repair_obsoletes=repair_obsoletes
        self.entity_map=entity_map
        self.valid_taxa=valid_taxa
        self.class_idspaces=class_idspaces
        self.include_relations=include_relations
        self.exclude_relations=exclude_relations
        self.filter_out_evidence = filter_out_evidence

class Report():
    """
    A report object that is generated as a result of a parse
    """

    # Levels
    FATAL = 'FATAL'
    ERROR = 'ERROR'
    WARNING = 'WARNING'

    # Warnings: TODO link to gorules
    INVALID_ID = "Invalid identifier"
    UNKNOWN_ID = "Unknown identifier"
    INVALID_IDSPACE = "Invalid identifier prefix"
    INVALID_TAXON = "Invalid taxon"
    UNMAPPED_ID = "Unmapped identifier"
    OBSOLETE_CLASS = "Obsolete class"
    OBSOLETE_CLASS_NO_REPLACEMENT = "Obsolete class with no replacement"
    WRONG_NUMBER_OF_COLUMNS = "Wrong number of columns in this line"

    """
    3 warning levels
    """
    LEVELS = [FATAL, ERROR, WARNING]

    def __init__(self):
        self.messages = []
        self.n_lines = 0
        self.n_assocs = 0
        self.skipped = []
        self.subjects = set()
        self.objects = set()
        self.taxa = set()
        self.references = set()

    def error(self, line, type, obj, msg=""):
        self.message(self.ERROR, line, type, obj, msg)
    def warning(self, line, type, obj, msg=""):
        self.message(self.WARNING, line, type, obj, msg)
    def message(self, level, line, type, obj, msg=""):
        self.messages.append({'level':level,
                              'line':line,
                              'type':type,
                              'message':msg,
                              'obj':obj})

    def to_report_json(self):
        """
        Generate a summary in json format
        """

        N = 10
        report = dict(
            summary = dict(association_count = self.n_assocs,
                           line_count = self.n_lines,
                           skipped_line_count = len(self.skipped)),
            aggregate_statistics = dict(subject_count=len(self.subjects),
                                        object_count=len(self.objects),
                                        taxon_count=len(self.taxa),
                                        reference_count=len(self.references),
                                        taxon_sample=list(self.taxa)[0:N],
                                        subject_sample=list(self.subjects)[0:N],
                                        object_sample=list(self.objects)[0:N])
        )

        # grouped messages
        gm = {}
        for level in self.LEVELS:
            gm[level] = []
        for m in self.messages:
            level = m['level']
            gm[level].append(m)

        mgroups = []
        for level in self.LEVELS:
            msgs = gm[level]
            mgroup = dict(level=level,
                          count=len(msgs),
                          messages=msgs)
            mgroups.append(mgroup)
        report['groups'] = mgroups
        return report

    def to_markdown(self):
        """
        Generate a summary in markdown format
        """
        json = self.to_report_json()
        summary = json['summary']

        s = ""
        s += "\n## SUMMARY\n\n"

        s += " * Associations: {}\n" . format(summary['association_count'])
        s += " * Lines in file (incl headers): {}\n" . format(summary['line_count'])
        s += " * Lines skipped: {}\n" . format(summary['skipped_line_count'])

        stats = json['aggregate_statistics']
        s += "\n## STATISTICS\n\n"
        for k,v in stats.items():
            s += " * {}: {}\n" . format(k,v)

        s += "\n## MESSAGES\n\n"
        for g in json['groups']:
            s += " * {}: {}\n".format(g['level'], g['count'])
        s += "\n\n"
        for g in json['groups']:
            level = g['level']
            msgs = g['messages']
            if len(msgs) > 0:
                s += "### {}\n\n".format(level)
                for m in msgs:
                    s += " * {}: obj:'{}' \"{}\" `{}`\n".format(m['type'],m['obj'],m['message'],m['line'])
        return s

# TODO avoid using names that are builtin python: file, id

class AssocParser():
    """
    Abstract superclass of all association parser classes
    """

    def parse(self, file, outfile=None):
        """Parse a line-oriented association file into a list of association dict objects

        Note the returned list is of dict objects. TODO: These will
        later be specified using marshmallow and it should be possible
        to generate objects

        Arguments
        ---------
        file : file or string
            The file is parsed into association objects. Can be a http URL, filename or `file-like-object`, for input assoc file
        outfile : file
            Optional output file in which processed lines are written. This a file or `file-like-object`

        Return
        ------
        list
            Associations generated from the file
        """
        file = self._ensure_file(file)
        assocs = []
        skipped = []
        n_lines = 0
        for line in file:
            n_lines += 1
            if line.startswith("!"):
                if outfile is not None:
                    outfile.write(line)
                continue
            line = line.strip("\n")
            if line == "":
                logging.warn("EMPTY LINE")
                continue

            parsed_line, new_assocs  = self.parse_line(line)
            if self._skipping_line(new_assocs): # Skip if there were no assocs
                logging.warn("SKIPPING: {}".format(line))
                skipped.append(line)
            else:
                for a in new_assocs:
                    self._validate_assoc(a)
                    rpt = self.report
                    rpt.subjects.add(a['subject']['id'])
                    rpt.objects.add(a['object']['id'])
                    rpt.references.update(a['evidence']['has_supporting_reference'])
                    if 'taxon' in a['subject']:
                        rpt.taxa.add(a['subject']['taxon']['id'])
                assocs += new_assocs
                if outfile is not None:
                    outfile.write(parsed_line + "\n")

        self.report.skipped += skipped
        self.report.n_lines += n_lines
        self.report.n_assocs += len(assocs)
        logging.info("Parsed {} assocs from {} lines. Skipped: {}".
                     format(len(assocs),
                            n_lines,
                            len(skipped)))
        file.close()
        return assocs

    def _validate_assoc(self, assoc):
        self._validate_ontology_class_id(assoc['object']['id'], assoc['source_line'])

    def map_to_subset(self, file, outfile=None, ontology=None, subset=None, class_map=None, relations=None):
        """
        Map a file to a subset, writing out results

        You can pass either a subset name (e.g. goslim_generic) or a dictionary with ready-made mappings

        Arguments
        ---------
        file: file
            Name or file object for input assoc file
        outfile: file
            Name or file object for output (mapped) assoc file; writes to stdout if not set
        subset: str
            Optional name of subset to map to, e.g. goslim_generic
        class_map: dict
            Mapping between asserted class ids and ids to map to. Many to many
        ontology: `Ontology`
            Ontology to extract subset from

        """
        if subset is not None:
            logging.info("Creating mapping for subset: {}".format(subset))
            class_map = ontology.create_slim_mapping(subset=subset, relations=relations)

        if class_map is None:
            raise ValueError("Neither class_map not subset is set")
        col = self.ANNOTATION_CLASS_COLUMN
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            logging.info("LINE: {} VALS: {}".format(line, vals))
            if len(vals) < col:
                raise ValueError("Line: {} has too few cols, expect class id in col {}".format(line, col))
            cid = vals[col]
            if cid not in class_map or len(class_map[cid]) == 0:
                self.report.error(line, Report.UNMAPPED_ID, cid)
                continue
            else:
                for mcid in class_map[cid]:
                    vals[col] = mcid
                    line = "\t".join(vals)
                    if outfile is not None:
                        outfile.write(line)
                    else:
                        print(line)


    def skim(self, file):
        """
        Lightweight parse of a file into tuples.

        Note this discards metadata such as evidence.

        Return a list of tuples (subject_id, subject_label, object_id)
        """
        raise NotImplementedError("AssocParser.skim not implemented")

    def parse_line(self, line):
        raise NotImplementedError("AssocParser.parse_line not implemented")

    def _skipping_line(self, associations):
        return associations is None or associations == []

    def _is_exclude_relation(self, relation):
        if self.config.include_relations is not None and len(self.config.include_relations)>0:
            if relation not in self.config.include_relations:
                return True
        if self.config.exclude_relations is not None and len(self.config.exclude_relations)>0:
            if relation in self.config.exclude_relations:
                return True
        return False

    ## we generate both qualifier and relation field
    ## Returns: (negated, relation, other_qualifiers)
    def _parse_qualifier(self, qualifier, aspect):
        relation = None
        qualifiers = qualifier.split("|")
        if qualifier == '':
            qualifiers = []
        negated =  'NOT' in qualifiers
        other_qualifiers = [q for q in qualifiers if q != 'NOT']
        ## In GAFs, relation is overloaded into qualifier.
        ## If no explicit non-NOT qualifier is specified, use
        ## a default based on GPI spec
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
        return (negated, relation, other_qualifiers)

    # split an ID/CURIE into prefix and local parts
    # (not currently used)
    def _parse_id(self, id):
        toks = id.split(":")
        if len(toks) == 2:
            return (toks[0],toks[1])
        else:
            return (toks[0],toks[1:].join(":"))

    # split an ID/CURIE into prefix and local parts
    def _get_id_prefix(self, id):
        toks = id.split(":")
        return toks[0]

    def _validate_taxon(self, taxon, line):
        if self.config.valid_taxa is None:
            return True
        else:
            if taxon in self.config.valid_taxa:
                return True
            else:
                self.report.error(line, Report.INVALID_TAXON, taxon)
                return False

    # check the term id is in the ontology, and is not obsolete
    def _validate_ontology_class_id(self, id, line, subclassof=None):
        ont = self.config.ontology
        if ont is None:
            return id
        if not ont.has_node(id):
            self.report.warning(line, Report.UNKNOWN_ID, id)
            return id
        if ont.is_obsolete(id):
            if self.config.repair_obsoletes:
                rb = ont.replaced_by(id, strict=False)
                if isinstance(rb,str):
                    self.report.warning(line, Report.OBSOLETE_CLASS, id)
                    id =  rb
                else:
                    self.report.warning(line, Report.OBSOLETE_CLASS_NO_REPLACEMENT, id)
            else:
                self.report.warning(line, Report.OBSOLETE_CLASS, id)
        # TODO: subclassof
        return id


    def _validate_id(self, id, line, context=None):
        if " " in id:
            self.report.error(line, Report.INVALID_ID, id, "contains spaces")
            return False
        if id.find("|") > -1:
            # non-fatal
            self.report.error('', Report.INVALID_ID, id, "contains pipe in unexpected place")
        idspace = self._get_id_prefix(id)
        if context == ANNOTATION and self.config.class_idspaces is not None:
            if idspace not in self.config.class_idspaces:
                self.report.error(line, Report.INVALID_IDSPACE, id, "allowed: {}".format(self.config.class_idspaces))
                return False
        return True

    def _split_pipe(self, v):
        if v == "":
            return []
        ids = v.split("|")
        ids = [id for id in ids if self._validate_id(id, '')]
        return ids

    def _pair_to_id(self, db, localid):
        if self.config.remove_double_prefixes:
            ## Switch MGI:MGI:n to MGI:n
            if localid.startswith(db+":"):
                localid = localid.replace(db+":","")
        return db + ":" + localid

    def _taxon_id(self,id):
         id = id.replace('taxon','NCBITaxon')
         self._validate_id(id,'',TAXON)
         return id

    def _ensure_file(self, file):
        if isinstance(file,str):
            # TODO Let's fix this if/elseif chain.
            if file.startswith("ftp"):
                f = tempfile.NamedTemporaryFile()
                fn = f.name
                cmd = ['wget',file,'-O',fn]
                subprocess.run(cmd, check=True)
                return open(fn,"r")
            elif file.startswith("http"):
                url = file
                with closing(requests.get(url, stream=False)) as resp:
                    logging.info("URL: {} STATUS: {} ".format(url, resp.status_code))
                    ok = resp.status_code == 200
                    if ok:
                        return io.StringIO(resp.text)
                    else:
                        return None
            else:
                 return open(file, "r")
        else:
            return file


    def _parse_class_expression(self, x):
        ## E.g. exists_during(GO:0000753)
        ## Atomic class expressions only
        [(p,v)] = re.findall('(.*)\((.*)\)',x)
        return {
            'property':p,
            'filler':v
        }

# TODO consider making an Association its own class too to give it a little more
# TODO Semantic value?

# TODO consider making an ID class?


class GpadParser(AssocParser):
    """
    Parser for GO GPAD Format

    https://github.com/geneontology/go-annotation/blob/master/specs/gpad-gpi-1_2.md
    """

    ANNOTATION_CLASS_COLUMN=3

    def __init__(self,config=None):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        if config == None:
            config = AssocParserConfig()
        self.config = config
        self.report = Report()

    def skim(self, file):
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if len(vals) != 12:
                logging.error("Unexpected number of columns: {}. GPAD should have 12.".format(vals))
            rel = vals[2]

            negated, relation, _ = self._parse_qualifier(vals[2], None)
            if negated:
                continue
            if self._is_exclude_relation(relation):
                continue


            id = self._pair_to_id(vals[0], vals[1])
            if not self._validate_id(id, line, ENTITY):
                continue
            t = vals[3]
            tuples.append( (id,None,t) )
        return tuples

    def parse_line(self, line):
        """Parses a single line of a GPAD.

        Return a tuple `(processed_line, associations)`. Typically
        there will be a single association, but in some cases there
        may be none (invalid line) or multiple (disjunctive clause in
        annotation extensions)

        Note: most applications will only need to call this directly if they require fine-grained control of parsing. For most purposes,
        :method:`parse_file` can be used over the whole file

        Arguments
        ---------
        line : str
            A single tab-seperated line from a GPAD file

        """
        vals = line.split("\t")
        [db,
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
         annotation_properties] = vals

        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, line, ENTITY):
            return line, []

        if not self._validate_id(goid, line, ANNOTATION):
            return line, []

        ## --
        ## qualifier
        ## --
        negated, relation, other_qualifiers = self._parse_qualifier(qualifier, None)

        assocs = []
        xp_ors = annotation_xp.split("|")
        for xp_or in xp_ors:
            xp_ands = xp_or.split(",")
            extns = []
            for xp_and in xp_ands:
                if xp_and != "":
                    extns.append(self._parse_class_expression(xp_and))
            assoc = {
                'source_line': line,
                'subject': {
                    'id':id
                },
                'object': {
                    'id':goid,
                    'extensions': extns
                },
                'negated': negated,
                'relation': {
                    'id': relation
                },
                'evidence': {
                    'type': evidence,
                    'with_support_from': self._split_pipe(withfrom),
                    'has_supporting_reference': self._split_pipe(reference)
                },
                'provided_by': assigned_by,
                'date': date,

            }
            if len(other_qualifiers) > 0:
                assoc['qualifiers'] = other_qualifiers
            assocs.append(assoc)
        return line, assocs

class GafParser(AssocParser):
    """
    Parser for GO GAF format
    """

    ANNOTATION_CLASS_COLUMN=4

    def __init__(self,config=None):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        if config == None:
            config = AssocParserConfig()
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
                logging.error("Unexpected number of vals: {}. GAFv1 has 15, GAFv2 has 17.".format(vals))

            negated, relation, _ = self._parse_qualifier(vals[3], vals[8])
            if negated:
                continue
            if self._is_exclude_relation(relation):
                continue
            id = self._pair_to_id(vals[0], vals[1])
            if not self._validate_id(id, line, ENTITY):
                continue
            n = vals[2]
            t = vals[4]
            tuples.append( (id,n,t) )
        return tuples


    def parse_line(self, line):
        """
        Parses a single line of a GAF

        Return a tuple `(processed_line, associations)`. Typically
        there will be a single association, but in some cases there
        may be none (invalid line) or multiple (disjunctive clause in
        annotation extensions)

        Note: most applications will only need to call this directly if they require fine-grained control of parsing. For most purposes,
        :method:`parse_file` can be used over the whole file

        Arguments
        ---------
        line : str
            A single tab-seperated line from a GPAD file

        """
        config = self.config

        vals = line.split("\t")

        if len(vals) != 15 and len(vals) != 17:
            self.report.error(line, Report.WRONG_NUMBER_OF_COLUMNS, "",
                msg="There were {columns} columns found in this line, and there should be 15 (for GAF v1) or 17 (for GAF v2)".format(len(vals)))
            return line, []

        # GAF v1 is defined as 15 cols, GAF v2 as 17.
        # We treat everything as GAF2 by adding two blank columns.
        # TODO: check header metadata to see if columns corresponds to declared dataformat version
        if len(vals) == 15:
            vals += ["",""]
        if len(vals) != 17:
            logging.error("Wrong number of lines: {}".format(lines))
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

        ## --
        ## db + db_object_id. CARD=1
        ## --
        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, line, ENTITY):
            return line, []

        if not self._validate_id(goid, line, ANNOTATION):
            return line, []

        # If the evidence code is one of the set we're filtering out (skipping)
        # then no association and return!
        if evidence.upper() in self.config.filter_out_evidence:
            return line, []

        # Example use case: mapping from UniProtKB to MOD ID
        if config.entity_map is not None:
            id = self.map_id(id, config.entity_map)
            toks = id.split(":")
            db = toks[0]
            db_object_id = toks[1:]
            vals[1] = db_object_id

        ## --
        ## end of line re-processing
        ## --
        # regenerate line post-mapping
        line = "\t".join(vals)

        ## --
        ## taxon CARD={1,2}
        ## --
        ## if a second value is specified, this is the interacting taxon
        taxa = [self._taxon_id(x) for x in taxon.split("|")]
        taxon = taxa[0]
        in_taxa = taxa[1:]
        self._validate_taxon(taxon, line)

        ## --
        ## db_object_synonym CARD=0..*
        ## --
        synonyms = db_object_synonym.split("|")
        if db_object_synonym == "":
            synonyms = []

        ## --
        ## process associations
        ## --
        ## note that any disjunctions in the annotation extension
        ## will result in the generation of multiple associations
        assocs = []
        xp_ors = annotation_xp.split("|")
        for xp_or in xp_ors:

            # gather conjunctive expressions in extensions field
            xp_ands = xp_or.split(",")
            extns = []
            for xp_and in xp_ands:
                if xp_and != "":
                    extns.append(self._parse_class_expression(xp_and))

            ## --
            ## qualifier
            ## --
            negated, relation, other_qualifiers = self._parse_qualifier(qualifier, aspect)

            ## --
            ## goid
            ## --
            # TODO We shouldn't overload buildin keywords/functions
            object = {'id':goid,
                      'taxon': taxon}

            # construct subject dict
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

            ## --
            ## gene_product_isoform
            ## --
            ## This is mapped to a more generic concept of subject_extensions
            subject_extns = []
            if gene_product_isoform is not None and gene_product_isoform != '':
                subject_extns.append({'property':'isoform', 'filler':gene_product_isoform})

            ## --
            ## evidence
            ## reference
            ## withfrom
            ## --
            evidence = {
                'type': evidence,
                'has_supporting_reference': self._split_pipe(reference)
            }
            evidence['with_support_from'] = self._split_pipe(withfrom)

            ## Construct main return dict
            assoc = {
                'source_line': line,
                'subject': subject,
                'object': object,
                'negated': negated,
                'qualifiers': other_qualifiers,
                'aspect': aspect,
                'relation': {
                    'id': relation
                },
                'evidence': evidence,
                'provided_by': assigned_by,
                'date': date,

            }
            if len(subject_extns) > 0:
                assoc['subject_extensions'] = subject_extns
            if len(extns) > 0:
                assoc['object_extensions'] = extns

            assocs.append(assoc)
        return line, assocs

class HpoaParser(GafParser):
    """
    Parser for HPOA format

    http://human-phenotype-ontology.github.io/documentation.html#annot

    Note that there are similarities with Gaf format, so we inherit from GafParser, and override
    """

    def __init__(self,config=None):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        if config == None:
            config = AssocParserConfig()
        self.config = config
        self.report = Report()

    def parse_line(self, line):
        """
        Parses a single line of a HPOA file

        Return a tuple `(processed_line, associations)`. Typically
        there will be a single association, but in some cases there
        may be none (invalid line) or multiple (disjunctive clause in
        annotation extensions)

        Note: most applications will only need to call this directly if they require fine-grained control of parsing. For most purposes,
        :method:`parse_file` can be used over the whole file

        Arguments
        ---------
        line : str
            A single tab-seperated line from a GPAD file

        """
        config = self.config

        # http://human-phenotype-ontology.github.io/documentation.html#annot
        vals = line.split("\t")
        [db,
         db_object_id,
         db_object_symbol,
         qualifier,
         hpoid,
         reference,
         evidence,
         onset,
         frequency,
         withfrom,
         aspect,
         db_object_synonym,
         date,
         assigned_by] = vals

        # hardcode this, as HPOA is currently human-only
        taxon = 'NCBITaxon:9606'

        # hardcode this, as HPOA is currently disease-only
        db_object_type = 'disease'

        ## --
        ## db + db_object_id. CARD=1
        ## --
        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, line, ENTITY):
            return line, []

        if not self._validate_id(hpoid, line, ANNOTATION):
            return line, []


        # Example use case: mapping from OMIM to Orphanet
        if config.entity_map is not None:
            id = self.map_id(id, config.entity_map)
            toks = id.split(":")
            db = toks[0]
            db_object_id = toks[1:]
            vals[1] = db_object_id

        ## --
        ## end of line re-processing
        ## --
        # regenerate line post-mapping
        line = "\t".join(vals)

        ## --
        ## db_object_synonym CARD=0..*
        ## --
        synonyms = db_object_synonym.split("|")
        if db_object_synonym == "":
            synonyms = []


        ## --
        ## qualifier
        ## --
        ## we generate both qualifier and relation field
        relation = None
        qualifiers = qualifier.split("|")
        if qualifier == '':
            qualifiers = []
        negated =  'NOT' in qualifiers
        other_qualifiers = [q for q in qualifiers if q != 'NOT']

        ## CURRENTLY NOT USED
        if len(other_qualifiers) > 0:
            relation = other_qualifiers[0]
        else:
            if aspect == 'O':
                relation = 'has_phenotype'
            elif aspect == 'I':
                relation = 'has_inheritance'
            elif aspect == 'M':
                relation = 'mortality'
            elif aspect == 'C':
                relation = 'has_onset'
            else:
                relation = None

        ## --
        ## hpoid
        ## --
        object = {'id':hpoid,
                  'taxon': taxon}

        # construct subject dict
        subject = {
            'id':id,
            'label':db_object_symbol,
            'type': db_object_type,
            'synonyms': synonyms,
            'taxon': {
                'id': taxon
            }
        }

        ## --
        ## evidence
        ## reference
        ## withfrom
        ## --
        evidence = {
            'type': evidence,
            'has_supporting_reference': reference.split("; ")
        }
        evidence['with_support_from'] = self._split_pipe(withfrom)

        ## Construct main return dict
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

        return line, [assoc]
