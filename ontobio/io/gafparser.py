import re
import logging
import json

from ontobio.io import assocparser
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION, Report
from ontobio.io import qc
from ontobio.io import entityparser
from ontobio.io import entitywriter

class GafParser(assocparser.AssocParser):
    """
    Parser for GO GAF format
    """

    ANNOTATION_CLASS_COLUMN=4

    def __init__(self, config=None, group="unknown", dataset="unknown"):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        self.config = config
        if config is None:
            self.config = assocparser.AssocParserConfig()
        self.report = assocparser.Report(group=group, dataset=dataset, config=self.config)
        self.gpi = None
        if self.config.gpi_authority_path is not None:
            self.gpi = dict()
            parser = entityparser.GpiParser()
            with open(self.config.gpi_authority_path) as gpi_f:
                entities = parser.parse(file=gpi_f)
                for entity in entities:
                    self.gpi[entity["id"]] = {
                        "symbol": entity["label"],
                        "name": entity["full_name"],
                        "synonyms": entitywriter.stringify(entity["synonyms"]),
                        "type": entity["type"]
                    }

                print("Loaded {} entities from {}".format(len(self.gpi.keys()), self.config.gpi_authority_path))

    def skim(self, file):
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if len(vals) < 15:
                logging.error("Unexpected number of vals: {}. GAFv1 has 15, GAFv2 has 17.".format(vals))

            split_line = assocparser.SplitLine(line=line, values=vals, taxon=vals[12])

            negated, relation, _ = self._parse_qualifier(vals[3], vals[8])

            # never include NOTs in a skim
            if negated:
                continue
            if self._is_exclude_relation(relation):
                continue
            id = self._pair_to_id(vals[0], vals[1])
            if not self._validate_id(id, split_line, context=ENTITY):
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
            return assocparser.ParseResult(line, [{ "header": True, "line": line.strip() }], False)

        vals = [el.strip() for el in line.split("\t")]

        # GAF v1 is defined as 15 cols, GAF v2 as 17.
        # We treat everything as GAF2 by adding two blank columns.
        # TODO: check header metadata to see if columns corresponds to declared dataformat version
        if 17 > len(vals) >= 15:
            vals += [""] * (17 - len(vals))

        if len(vals) > 17:
            # If we see more than 17 columns, we will just cut off the columns after column 17
            self.report.warning(line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
                msg="There were more than 17 columns in this line. Proceeding by cutting off extra columns after column 17.",
                rule=1)
            vals = vals[:17]


        if len(vals) != 17:
            self.report.error(line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
                msg="There were {columns} columns found in this line, and there should be 15 (for GAF v1) or 17 (for GAF v2)".format(columns=len(vals)),
                rule=1)
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

        split_line = assocparser.SplitLine(line=line, values=vals, taxon=taxon)

        ## check for missing columns
        if db == "":
            self.report.error(line, Report.INVALID_IDSPACE, "EMPTY", "col1 is empty", taxon=taxon, rule=1)
            return assocparser.ParseResult(line, [], True)
        if db_object_id == "":
            self.report.error(line, Report.INVALID_ID, "EMPTY", "col2 is empty", taxon=taxon, rule=1)
            return assocparser.ParseResult(line, [], True)
        if taxon == "":
            self.report.error(line, Report.INVALID_TAXON, "EMPTY", "taxon column is empty", taxon=taxon, rule=1)
            return assocparser.ParseResult(line, [], True)
        if reference == "":
            self.report.error(line, Report.INVALID_ID, "EMPTY", "reference column 6 is empty", taxon=taxon, rule=1)
            return assocparser.ParseResult(line, [], True)

        if self.config.group_idspace is not None and assigned_by not in self.config.group_idspace:
            self.report.warning(line, Report.INVALID_ID, assigned_by,
                "GORULE:0000027: assigned_by is not present in groups reference", taxon=taxon, rule=27)

        ## --
        ## db + db_object_id. CARD=1
        ## --
        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, split_line, allowed_ids=self.config.entity_idspaces):
            return assocparser.ParseResult(line, [], True)

        # Using a given gpi file to validate the gene object
        if self.gpi is not None:
            entity = self.gpi.get(id, None)
            if entity is not None:
                db_object_symbol = entity["symbol"]
                db_object_name = entity["name"]
                db_object_synonym = entity["synonyms"]
                db_object_type = entity["type"]

        if not self._validate_id(goid, split_line, context=ANNOTATION):
            print("skipping because {} not validated!".format(goid))
            return assocparser.ParseResult(line, [], True)

        valid_goid = self._validate_ontology_class_id(goid, split_line)
        if valid_goid == None:
            return assocparser.ParseResult(line, [], True)
        goid = valid_goid

        date = self._normalize_gaf_date(date, split_line)
        if date == None:
            return assocparser.ParseResult(line, [], True)

        vals[13] = date

        ecomap = self.config.ecomap
        if ecomap is not None:
            if ecomap.coderef_to_ecoclass(evidence, reference) is None:
                self.report.error(line, assocparser.Report.UNKNOWN_EVIDENCE_CLASS, evidence,
                                msg="Expecting a known ECO GAF code, e.g ISS", rule=1)
                return assocparser.ParseResult(line, [], True)

        # Throw out the line if it uses GO_REF:0000033, see https://github.com/geneontology/go-site/issues/563#event-1519351033
        if "GO_REF:0000033" in reference.split("|"):
            self.report.error(line, assocparser.Report.INVALID_ID, reference,
                                msg="Disallowing GO_REF:0000033 in reference field as of 03/13/2018", rule=30)
            return assocparser.ParseResult(line, [], True)

        references = self.validate_pipe_separated_ids(reference, split_line)
        if references == None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)

        # With/From
        withfroms = self.validate_pipe_separated_ids(withfrom, split_line, empty_allowed=True, extra_delims=",")
        if withfroms == None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)

        # validation
        self._validate_symbol(db_object_symbol, split_line)

        # Example use case: mapping from UniProtKB to MOD ID
        if self.config.entity_map is not None:
            id = self.map_id(id, self.config.entity_map)
            toks = id.split(":")
            db = toks[0]
            db_object_id = toks[1:]
            vals[1] = db_object_id

        if goid.startswith("GO:") and aspect.upper() not in ["C", "F", "P"]:
            self.report.error(line, assocparser.Report.INVALID_ASPECT, aspect, rule=28)
            return assocparser.ParseResult(line, [], True)


        go_rule_results = qc.test_go_rules(vals, self.config)
        for rule_id, result in go_rule_results.items():
            if result.result_type == qc.ResultType.WARNING:
                self.report.warning(line, assocparser.Report.VIOLATES_GO_RULE, goid,
                                    msg="{id}: {message}".format(id=rule_id, message=result.message), rule=int(rule_id.split(":")[1]))
                # Skip the annotation
                return assocparser.ParseResult(line, [], True)

            if result.result_type == qc.ResultType.ERROR:
                self.report.error(line, assocparser.Report.VIOLATES_GO_RULE, goid,
                                    msg="{id}: {message}".format(id=rule_id, message=result.message), rule=int(rule_id.split(":")[1]))
                # Skip the annotation
                return assocparser.ParseResult(line, [], True)

        ## --
        ## end of line re-processing
        ## --
        # regenerate line post-mapping
        line = "\t".join(vals)

        ## --
        ## taxon CARD={1,2}
        ## --
        ## if a second value is specified, this is the interacting taxon
        ## We do not use the second value
        taxons = taxon.split("|")
        normalized_taxon = self._taxon_id(taxons[0], split_line)
        if normalized_taxon == None:
            self.report.error(line, assocparser.Report.INVALID_TAXON, taxon,
                                msg="Taxon ID is invalid")
            return assocparser.ParseResult(line, [], True)

        self._validate_taxon(normalized_taxon, split_line)

        interacting_taxon = None
        if len(taxons) == 2:
            interacting_taxon = self._taxon_id(taxons[1], split_line)
            if interacting_taxon == None:
                self.report.error(line, assocparser.Report.INVALID_TAXON, taxon,
                                    msg="Taxon ID is invalid")
                return assocparser.ParseResult(line, [], True)

        ## --
        ## db_object_synonym CARD=0..*
        ## --
        synonyms = db_object_synonym.split("|")
        if db_object_synonym == "":
            synonyms = []

        ## --
        ## parse annotation extension
        ## See appendix in http://doi.org/10.1186/1471-2105-15-155
        ## --
        object_or_exprs = self._parse_full_extension_expression(annotation_xp, line=split_line)

        ## --
        ## qualifier
        ## --
        negated, relation, other_qualifiers = self._parse_qualifier(qualifier, aspect)

        ## --
        ## goid
        ## --
        # TODO We shouldn't overload buildin keywords/functions
        object = {'id': goid,
                  'taxon': normalized_taxon}

        # construct subject dict
        subject = {
            'id': id,
            'label': db_object_symbol,
            'type': db_object_type,
            'fullname': db_object_name,
            'synonyms': synonyms,
            'taxon': {
                'id': normalized_taxon
            }
        }

        ## --
        ## gene_product_isoform
        ## --
        ## This is mapped to a more generic concept of subject_extensions
        subject_extns = []
        if gene_product_isoform is not None and gene_product_isoform != '':
            subject_extns.append({'property': 'isoform', 'filler': gene_product_isoform})

        object_extensions = {}
        if object_or_exprs is not None and len(object_or_exprs) > 0:
            object_extensions['union_of'] = object_or_exprs

        ## --
        ## evidence
        ## reference
        ## withfrom
        ## --
        evidence_obj = {
            'type': evidence,
            'has_supporting_reference': references,
            'with_support_from': withfroms
        }

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
            'interacting_taxon': interacting_taxon,
            'evidence': evidence_obj,
            'provided_by': assigned_by,
            'date': date,
            'subject_extensions': subject_extns,
            'object_extensions': object_extensions
        }

        return assocparser.ParseResult(line, [assoc], False, evidence.upper())
