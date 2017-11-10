import re
import logging
import json

from ontobio.io import assocparser
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION

class GafParser(assocparser.AssocParser):
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
            config = assocparser.AssocParserConfig()
        self.config = config
        self.report = assocparser.Report()

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

            # never include NOTs in a skim
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
            A single tab-seperated line from a GAF file

        """

        # Returns assocparser.ParseResult
        parsed = super().validate_line(line)
        if parsed:
            return parsed

        if self.is_header(line):
            return assocparser.ParseResult(line, [], False)

        vals = [el.strip() for el in line.split("\t")]

        # GAF v1 is defined as 15 cols, GAF v2 as 17.
        # We treat everything as GAF2 by adding two blank columns.
        # TODO: check header metadata to see if columns corresponds to declared dataformat version
        if 17 > len(vals) >= 15:
            vals += [""] * (17 - len(vals))

        if len(vals) != 17:
            self.report.error(line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
                msg="There were {columns} columns found in this line, and there should be 15 (for GAF v1) or 17 (for GAF v2)".format(columns=len(vals)))
            return assocparser.ParseResult(line, [], True)

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
            print("skipping cause {} not validated!".format(id))
            return assocparser.ParseResult(line, [], True)

        if not self._validate_id(goid, line, ANNOTATION):
            print("skipping cause {} not validated!".format(goid))
            return assocparser.ParseResult(line, [], True)

        date = self._normalize_gaf_date(date, line)

        ecomap = self.config.ecomap
        if ecomap != None:
            if ecomap.coderef_to_ecoclass(evidence, reference) is None:
                self.report.error(line, assocparser.Report.UNKNOWN_EVIDENCE_CLASS, evidence,
                                msg="Expecting a known ECO GAF code, e.g ISS")
                return assocparser.ParseResult(line, [], True)

        # validation
        self._validate_symbol(db_object_symbol, line)

        # Example use case: mapping from UniProtKB to MOD ID
        if self.config.entity_map is not None:
            id = self.map_id(id, self.config.entity_map)
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
                    expr = self._parse_relationship_expression(xp_and, line=line)
                    if expr is not None:
                        extns.append(expr)

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
            evidence_obj = {
                'type': evidence,
                'has_supporting_reference': self._split_pipe(reference)
            }
            evidence_obj['with_support_from'] = self._split_pipe(withfrom)

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
                'evidence': evidence_obj,
                'provided_by': assigned_by,
                'date': date,

            }
            if len(subject_extns) > 0:
                assoc['subject_extensions'] = subject_extns
            if len(extns) > 0:
                assoc['object_extensions'] = extns

            self._validate_assoc(assoc, line)

            assocs.append(assoc)

        return assocparser.ParseResult(line, assocs, False, evidence.upper())

    def is_header(self, line):
        return line.startswith("!")
