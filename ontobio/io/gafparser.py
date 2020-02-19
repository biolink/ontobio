import re
import logging
import json

from typing import List, Tuple

from prefixcommons import curie_util

from ontobio.io import assocparser
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION, Report
from ontobio.io import qc
from ontobio.io import entityparser
from ontobio.io import entitywriter
from ontobio.model import association
from ontobio.ecomap import EcoMap
from ontobio.rdfgen import relations


import click

logger = logging.getLogger(__name__)


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
        self.group = group
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
                logger.error("Unexpected number of vals: {}. GAFv1 has 15, GAFv2 has 17.".format(vals))

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

        parsed = to_association(list(vals), report=self.report)
        if parsed.associations == []:
            return parsed

        assoc = parsed.associations[0]
        # self.report = parsed.report
        ## Run GO Rules, save split values into individual variables
        go_rule_results = qc.test_go_rules(assoc, self.config, group=self.group)
        for rule, result in go_rule_results.all_results.items():
            if result.result_type == qc.ResultType.WARNING:
                self.report.warning(line, assocparser.Report.VIOLATES_GO_RULE, "",
                                    msg="{id}: {message}".format(id=rule.id, message=result.message), rule=int(rule.id.split(":")[1]))

            if result.result_type == qc.ResultType.ERROR:
                self.report.error(line, assocparser.Report.VIOLATES_GO_RULE, "",
                                    msg="{id}: {message}".format(id=rule.id, message=result.message), rule=int(rule.id.split(":")[1]))
                # Skip the annotation
                return assocparser.ParseResult(line, [], True)

            if result.result_type == qc.ResultType.PASS:
                self.report.message(assocparser.Report.INFO, line, Report.RULE_PASS, "",
                                    msg="Passing Rule", rule=int(rule.id.split(":")[1]))

        vals = list(go_rule_results.annotation.to_gaf_tsv())
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

        if self.config.group_idspace is not None and assigned_by not in self.config.group_idspace:
            self.report.warning(line, Report.INVALID_ID, assigned_by,
                "GORULE:0000027: assigned_by is not present in groups reference", taxon=taxon, rule=27)

        if self.config.entity_idspaces is not None and db not in self.config.entity_idspaces:
            # Are we a synonym?
            upgrade = self.config.entity_idspaces.reverse(db)
            if upgrade is not None:
                # If we found a synonym
                self.report.warning(line, Report.INVALID_ID_DBXREF, db, "GORULE:0000027: {} is a synonym for the correct ID {}, and has been updated".format(db, upgrade), taxon=taxon, rule=27)
                db = upgrade

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

ecomap = EcoMap()
ecomap.mappings()
relation_tuple = re.compile(r'(.+)\((.+)\)')
def to_association(gaf_line: List[str], report=None, group="unknown", dataset="unknown") -> assocparser.ParseResult:
    report = Report(group=group, dataset=dataset) if report is None else report
    source_line = "\t".join(gaf_line)

    if source_line == "":
        report.error(source_line, "Blank Line", "EMPTY", "Blank lines are not allowed", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    if len(gaf_line) > 17:
        # If we see more than 17 columns, we will just cut off the columns after column 17
        report.warning(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were more than 17 columns in this line. Proceeding by cutting off extra columns after column 17.",
            rule=1)
        gaf_line = gaf_line[:17]

    if 17 > len(gaf_line) >= 15:
        gaf_line += [""] * (17 - len(gaf_line))

    if len(gaf_line) != 17:
        report.error(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were {columns} columns found in this line, and there should be 15 (for GAF v1) or 17 (for GAF v2)".format(columns=len(gaf_line)),
            rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    ## check for missing columns
    ## We use indeces here because we run GO RULES before we split the vals into individual variables
    DB_INDEX = 0
    DB_OBJECT_INDEX = 1
    TAXON_INDEX = 12
    REFERENCE_INDEX = 5
    if gaf_line[DB_INDEX] == "":
        report.error(source_line, Report.INVALID_IDSPACE, "EMPTY", "col1 is empty", taxon=gaf_line[TAXON_INDEX], rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)
    if gaf_line[DB_OBJECT_INDEX] == "":
        report.error(source_line, Report.INVALID_ID, "EMPTY", "col2 is empty", taxon=gaf_line[TAXON_INDEX], rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)
    if gaf_line[TAXON_INDEX] == "":
        report.error(source_line, Report.INVALID_TAXON, "EMPTY", "taxon column is empty", taxon=gaf_line[TAXON_INDEX], rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)
    if gaf_line[REFERENCE_INDEX] == "":
        report.error(source_line, Report.INVALID_ID, "EMPTY", "reference column 6 is empty", taxon=gaf_line[TAXON_INDEX], rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    taxon = gaf_line[12].split("|")
    taxon_curie = taxon[0].replace("taxon", "NCBITaxon")
    interacting_taxon = taxon[1].replace("taxon", "NCBITaxon") if len(taxon) == 2 else None
    subject_curie = "{db}:{id}".format(db=gaf_line[0], id=gaf_line[1])
    subject = association.Subject(subject_curie, gaf_line[2], gaf_line[9], gaf_line[10].split("|"), gaf_line[11], taxon_curie)
    aspect = gaf_line[8]
    negated, relation, qualifiers = assocparser._parse_qualifier(gaf_line[3], aspect)
    object = association.Term(gaf_line[4], taxon_curie)
    evidence = association.Evidence(
        ecomap.coderef_to_ecoclass(gaf_line[6]),
        [e for e in gaf_line[5].split("|") if e],
        [e for e in gaf_line[7].split("|") if e]
    )
    subject_extensions = [association.ExtensionUnit("rdfs:subClassOf", gaf_line[16])] if gaf_line[16] else []

    conjunctions = []
    if gaf_line[15]:
        for conjuncts in gaf_line[15].split("|"):
            extension_units = []
            for u in conjuncts.split(","):
                parsed = relation_tuple.findall(u)
                if len(parsed) == 1:
                    rel, term = parsed[0]
                    extension_units.append(association.ExtensionUnit(rel, term))
                else:
                    # Otherwise, something went bad with the regex, and it's a bad parse
                    report.error(source_line, Report.EXTENSION_SYNTAX_ERROR, u, "extensions should be relation(curie)", taxon=taxon, rule=1)
                    return assocparser.ParseResult(source_line, [], True, report=report)

            conjunction = association.ExtensionConjunctions(extension_units)
            conjunctions.append(conjunction)
    object_extensions = association.ExtensionExpression(conjunctions)
    looked_up_rel = relations.lookup_label(relation)
    if looked_up_rel is None:
        report.error(source_line, assocparser.Report.INVALID_QUALIFIER, relation, "Qualifer must be \"colocalizes_with\", \"contributes_to\", or \"NOT\"", taxon=taxon, rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    a = association.GoAssociation(
        source_line="\t".join(gaf_line),
        subject=subject,
        relation=curie_util.contract_uri(looked_up_rel)[0],
        object=object,
        negated=negated,
        qualifiers=qualifiers,
        aspect=aspect,
        interacting_taxon=interacting_taxon,
        evidence=evidence,
        subject_extensions=subject_extensions,
        object_extensions=object_extensions,
        provided_by=gaf_line[14],
        date=gaf_line[13],
        properties={})

    return assocparser.ParseResult(source_line, [a], False, report=report)
