from ontobio.io import assocparser
from ontobio.io import entityparser
from ontobio.io import entitywriter
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION, Report
from ontobio.io import parser_version_regex
from ontobio.io import qc
from ontobio.model import association, collections

from ontobio.rdfgen import relations
from prefixcommons import curie_util

from typing import List, Dict, Optional
from dataclasses import dataclass

import functools
import re
import logging

logger = logging.getLogger(__name__)


gpad_line_validators = {
    "default": assocparser.ColumnValidator(),
    "qualifier2_1": assocparser.Qualifier2_1(),
    "qualifier2_2": assocparser.Qualifier2_2(),
    "curie": assocparser.CurieValidator(),
    "taxon": assocparser.TaxonValidator(),
}

class GpadParser(assocparser.AssocParser):
    """
    Parser for GO GPAD Format

    https://github.com/geneontology/go-annotation/blob/master/specs/gpad-gpi-1_2.md
    """


    def __init__(self, config=assocparser.AssocParserConfig(), group="unknown", dataset="unknown", bio_entities=None):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        self.config = config
        self.report = assocparser.Report(config=self.config, group="unknown", dataset="unknown")
        self.version = None
        self.default_version = "1.2"
        self.bio_entities = bio_entities
        if self.bio_entities is None:
            self.bio_entities = collections.BioEntities(dict())
        if self.config.gpi_authority_path is not None:
            gpi_paths = self.config.gpi_authority_path
            if isinstance(gpi_paths, str):
                gpi_paths = [gpi_paths]
            for gpi_path in gpi_paths:
                gpi_bio_entities = collections.BioEntities.load_from_file(gpi_path)
                self.bio_entities.merge(gpi_bio_entities)
                print("Loaded {} entities from {}".format(len(gpi_bio_entities.entities.keys()), gpi_path))
        # self.gpi = dict()
        # if self.config.gpi_authority_path is not None:
        #     print("Loading GPI...")
        #     self.gpi = dict()
        #     parser = entityparser.GpiParser()
        #     with open(self.config.gpi_authority_path) as gpi_f:
        #         entities = parser.parse(file=gpi_f)
        #         for entity in entities:
        #             self.gpi[entity["id"]] = {
        #                 "symbol": entity["label"],
        #                 "name": entity["full_name"],
        #                 "synonyms": entitywriter.stringify(entity["synonyms"]),
        #                 "type": entity["type"]
        #             }
        #         print("Loaded {} entities from {}".format(len(self.gpi.keys()), self.config.gpi_authority_path))

    def gpad_version(self) -> str:
        if self.version:
            return self.version
        else:
            return self.default_version

    def skim(self, file):
        file = self._ensure_file(file)
        tuples = []
        for line in file:
            if line.startswith("!"):
                continue
            vals = line.split("\t")
            if len(vals) != 12:
                logger.error("Unexpected number of columns: {}. GPAD should have 12.".format(vals))
            rel = vals[2]

            negated, relation, _ = self._parse_qualifier(vals[2], None)

            # never include NOTs in a skim
            if negated:
                continue
            if self._is_exclude_relation(relation):
                continue


            id = self._pair_to_id(vals[0], vals[1])
            if not self._validate_id(id, line, context=ENTITY):
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
        parsed = super().validate_line(line)
        if parsed:
            return parsed

        if self.is_header(line):
            if self.version is None:
                # We are still looking
                parsed = parser_version_regex.findall(line)
                if len(parsed) == 1:
                    filetype, version, _ = parsed[0]
                    if version == "2.0":
                        logger.info("Detected GPAD version 2.0")
                        self.version = version
                    else:
                        logger.info("Detected GPAD version {}, so defaulting to 1.2".format(version))
                        self.version = self.default_version

            return assocparser.ParseResult(line, [{ "header": True, "line": line.strip() }], False)

        # At this point, we should have gone through all the header, and a version number should be established
        if self.version is None:
            logger.warning("No version number found for this file so we will assume GPAD version: {}".format(self.default_version))
            self.version = self.default_version

        vals = [el.strip() for el in line.split("\t")]

        parsed = to_association(list(vals), report=self.report, version=self.gpad_version(), bio_entities=self.bio_entities)
        if parsed.associations == []:
            return parsed

        assoc = parsed.associations[0]

        go_rule_results = qc.test_go_rules(assoc, self.config)
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

        assoc = go_rule_results.annotation  # type: association.GoAssociation

        split_line = assocparser.SplitLine(line=line, values=vals, taxon="")

        if not self._validate_id(str(assoc.subject.id), split_line, context=ENTITY):
            return assocparser.ParseResult(line, [], True)

        if not self._validate_id(str(assoc.object.id), split_line, context=ANNOTATION):
            return assocparser.ParseResult(line, [], True)

        valid_goid = self._validate_ontology_class_id(str(assoc.object.id), split_line)
        if valid_goid is None:
            return assocparser.ParseResult(line, [], True)
        assoc.object.id = association.Curie.from_str(valid_goid)

        if not self._validate_id(str(assoc.evidence.type), split_line):
            return assocparser.ParseResult(line, [], True)

        if assoc.interacting_taxon:
            if not self._validate_taxon(str(assoc.interacting_taxon), split_line):
                self.report.error(line, assocparser.Report.INVALID_TAXON, str(assoc.interacting_taxon), "Taxon ID is invalid", rule=27)
                return assocparser.ParseResult(line, [], True)


        #TODO: ecomap is currently one-way only
        #ecomap = self.config.ecomap
        #if ecomap != None:
        #    if ecomap.ecoclass_to_coderef(evidence) == (None,None):
        #        self.report.error(line, Report.UNKNOWN_EVIDENCE_CLASS, evidence,
        #                          msg="Expecting a known ECO class ID")


        # Reference Column
        references = self.validate_curie_ids(assoc.evidence.has_supporting_reference, split_line)
        if references is None:
            return assocparser.ParseResult(line, [], True)

        # With/From
        for wf in assoc.evidence.with_support_from:
            validated = self.validate_curie_ids(wf.elements, split_line)
            if validated is None:
                return assocparser.ParseResult(line, [], True)


        return assocparser.ParseResult(line, [assoc], False)

    def is_header(self, line):
        return line.startswith("!")


relation_tuple = re.compile(r'(.+)\((.+)\)')

def from_1_2(gpad_line: List[str], report=None, group="unknown", dataset="unknown", bio_entities=None):
    source_line = "\t".join(gpad_line)

    if source_line == "":
        report.error(source_line, "Blank Line", "EMPTY", "Blank lines are not allowed", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    if len(gpad_line) > 12:
        report.warning(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were more than 12 columns in this line. Proceeding by cutting off extra columns.",
            rule=1)

        gpad_line = gpad_line[:12]

    if 12 > len(gpad_line) >= 10:
        gpad_line += [""] * (12 - len(gpad_line))

    if len(gpad_line) != 12:
        report.error(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were {columns} columns found in this line, and there should be between 10 and 12".format(columns=len(gpad_line)), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    ## check for missing columns
    ## We use indeces here because we run GO RULES before we split the vals into individual variables
    DB_INDEX = 0
    DB_OBJECT_INDEX = 1
    QUALIFIER = 2
    REFERENCE_INDEX = 4
    EVIDENCE_INDEX = 5
    if gpad_line[DB_INDEX] == "":
        report.error(source_line, Report.INVALID_IDSPACE, "EMPTY", "col1 is empty", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)
    if gpad_line[DB_OBJECT_INDEX] == "":
        report.error(source_line, Report.INVALID_ID, "EMPTY", "col2 is empty", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)
    if gpad_line[QUALIFIER] == "":
        report.error(source_line, Report.INVALID_TAXON, "EMPTY", "qualifier column is empty", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)
    if gpad_line[REFERENCE_INDEX] == "":
        report.error(source_line, Report.INVALID_ID, "EMPTY", "reference column is empty", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)
    if gpad_line[EVIDENCE_INDEX] == "":
        report.error(source_line, Report.INVALID_ID, "EMPTY", "Evidence column is empty", rule=1)

    taxon = association.Curie("NCBITaxon", "0")
    subject_curie = association.Curie(gpad_line[0], gpad_line[1])
    subject = association.Subject(subject_curie, "", [""], [], [], taxon)

    entity = bio_entities.get(subject_curie)
    if entity is not None:
        subject = entity
        taxon = subject.taxon

    go_term = association.Curie.from_str(gpad_line[3])
    if go_term.is_error():
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[3], "Problem parsing GO Term", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    object = association.Term(go_term, taxon)

    evidence_type = association.Curie.from_str(gpad_line[5])
    if evidence_type.is_error():
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[5], "Problem parsing Evidence ECO Curie", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    references = [association.Curie.from_str(e) for e in gpad_line[4].split("|") if e]
    for r in references:
        if r.is_error():
            report.error(source_line, Report.INVALID_SYMBOL, gpad_line[4], "Problem parsing references", taxon=str(taxon), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    withfroms = association.ConjunctiveSet.str_to_conjunctions(gpad_line[6])  # Returns a list of ConjuctiveSets or Error
    if isinstance(withfroms, association.Error):
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[6], "Problem parsing With/From column", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    evidence = association.Evidence(evidence_type, references, withfroms)

    # Guarenteed to have at least one element, from above check
    raw_qs = gpad_line[QUALIFIER].split("|")
    negated = "NOT" in raw_qs

    looked_up_qualifiers = [relations.lookup_label(q) for q in raw_qs if q != "NOT"]
    if None in looked_up_qualifiers:
        report.error(source_line, Report.INVALID_QUALIFIER, raw_qs, "Could not find a URI for qualifier", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    qualifiers = [association.Curie.from_str(curie_util.contract_uri(q)[0]) for q in looked_up_qualifiers]

    date = assocparser.parse_date(gpad_line[8], report, source_line)
    if date is None:
        return assocparser.ParseResult(source_line, [], True, report=report)

    interacting_taxon = None
    if gpad_line[7]:
        taxon_result = gpad_line_validators["taxon"].validate(gpad_line[7])
        if not taxon_result.valid:
            report.error(source_line, Report.INVALID_TAXON, taxon_result.original, taxon_result.message, taxon=str(taxon_result.original), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)
        else:
            interacting_taxon = taxon_result.parsed[0]

    conjunctions = []
    if gpad_line[10]:
        conjunctions = association.ConjunctiveSet.str_to_conjunctions(
            gpad_line[10],
            conjunct_element_builder=lambda el: association.ExtensionUnit.from_str(el))

        if isinstance(conjunctions, association.Error):
            report.error(source_line, Report.EXTENSION_SYNTAX_ERROR, conjunctions.info, "extensions should be relation(curie)", taxon=str(taxon), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    properties_list = association.parse_annotation_properties(gpad_line[11])


    # print(properties_list)
    a = association.GoAssociation(
        source_line=source_line,
        subject=subject,
        relation=qualifiers[0],
        object=object,
        negated=negated,
        qualifiers=qualifiers,
        aspect=None,
        interacting_taxon=interacting_taxon,
        evidence=evidence,
        subject_extensions=[],
        object_extensions=conjunctions,
        provided_by=gpad_line[9],
        date=date,
        properties=properties_list)

    return assocparser.ParseResult(source_line, [a], False, report=report)

def from_2_0(gpad_line: List[str], report=None, group="unknown", dataset="unknown", bio_entities=None):
    source_line = "\t".join(gpad_line)

    if source_line == "":
        report.error(source_line, "Blank Line", "EMPTY", "Blank lines are not allowed", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    if len(gpad_line) > 12:
        report.warning(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were more than 12 columns in this line. Proceeding by cutting off extra columns.",
            rule=1)

        gpad_line = gpad_line[:12]

    if 12 > len(gpad_line) >= 10:
        gpad_line += [""] * (12 - len(gpad_line))

    if len(gpad_line) != 12:
        report.error(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were {columns} columns found in this line, and there should be between 10 and 12".format(columns=len(gpad_line)), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    ## check for missing columns
    ## We use indeces here because we run GO RULES before we split the vals into individual variables
    SUBJECT_CURIE = 0
    RELATION = 2
    ONTOLOGY_CLASS_INDEX = 3
    REFERENCE_INDEX = 4
    EVIDENCE_INDEX = 5
    DATE_INDEX = 8
    ASSIGNED_BY_INDEX = 9
    required = [SUBJECT_CURIE, RELATION, ONTOLOGY_CLASS_INDEX, REFERENCE_INDEX, EVIDENCE_INDEX, DATE_INDEX, ASSIGNED_BY_INDEX]
    for req in required:
        if gpad_line[req] == "":
            report.error(source_line, Report.INVALID_ID, "EMPTY", "Column {} is empty".format(req + 1), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    taxon = association.Curie("NCBITaxon", "0")
    subject_curie = association.Curie.from_str(gpad_line[SUBJECT_CURIE])
    if subject_curie.is_error():
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[SUBJECT_CURIE], "Problem parsing DB Object", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    subject = association.Subject(subject_curie, "", "", [], "", taxon)
    entity = bio_entities.get(subject_curie)
    if entity is not None:
        # If we found a subject entity, then set `subject` to the found entity
        subject = entity
        taxon = subject.taxon

    negated = gpad_line[1] == "NOT"

    relation = association.Curie.from_str(gpad_line[RELATION])
    if relation.is_error():
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[RELATION], "Problem parsing Relation", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    go_term = association.Curie.from_str(gpad_line[ONTOLOGY_CLASS_INDEX])
    if go_term.is_error():
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[ONTOLOGY_CLASS_INDEX], "Problem parsing GO Term", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    object = association.Term(go_term, taxon)

    evidence_type = association.Curie.from_str(gpad_line[EVIDENCE_INDEX])
    if evidence_type.is_error():
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[EVIDENCE_INDEX], "Problem parsing Evidence ECO Curie", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    references = [association.Curie.from_str(e) for e in gpad_line[REFERENCE_INDEX].split("|") if e]
    for r in references:
        if r.is_error():
            report.error(source_line, Report.INVALID_SYMBOL, gpad_line[REFERENCE_INDEX], "Problem parsing references", taxon=str(taxon), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    withfroms = association.ConjunctiveSet.str_to_conjunctions(gpad_line[6])  # Returns a list of ConjuctiveSets or Error
    if isinstance(withfroms, association.Error):
        report.error(source_line, Report.INVALID_SYMBOL, gpad_line[6], "Problem parsing With/From column", taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    evidence = association.Evidence(evidence_type, references, withfroms)

    interacting_taxon = None
    if gpad_line[7] != "":
        interacting_taxon = association.Curie.from_str(gpad_line[7])
        if interacting_taxon.is_error():
            report.error(source_line, Report.INVALID_SYMBOL, gpad_line[7], "Problem parsing Interacting Taxon", taxon=str(taxon), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    date = assocparser.parse_iso_date(gpad_line[DATE_INDEX], report, source_line)
    if date is None:
        return assocparser.ParseResult(source_line, [], True, report=report)

    conjunctions = []
    # The elements of the extension units are Curie(Curie)
    if gpad_line[10]:
        conjunctions = association.ConjunctiveSet.str_to_conjunctions(
            gpad_line[10],
            conjunct_element_builder=lambda el: association.ExtensionUnit.from_curie_str(el))

        if isinstance(conjunctions, association.Error):
            report.error(source_line, Report.EXTENSION_SYNTAX_ERROR, conjunctions.info, "extensions should be relation(curie)", taxon=str(taxon), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    properties_list = association.parse_annotation_properties(gpad_line[11])

    a = association.GoAssociation(
        source_line=source_line,
        subject=subject,
        relation=relation,
        object=object,
        negated=negated,
        qualifiers=[relation],
        aspect=None,
        interacting_taxon=interacting_taxon,
        evidence=evidence,
        subject_extensions=[],
        object_extensions=conjunctions,
        provided_by=gpad_line[9],
        date=date,
        properties=properties_list)

    return assocparser.ParseResult(source_line, [a], False, report=report)

def to_association(gpad_line: List[str], report=None, group="unknown", dataset="unknown", version="1.2", bio_entities=None) -> assocparser.ParseResult:
    report = Report(group=group, dataset=dataset) if report is None else report
    bio_entities = collections.BioEntities(dict()) if bio_entities is None else bio_entities
    if version == "2.0":
        return from_2_0(gpad_line, report=report, group=group, dataset=dataset, bio_entities=bio_entities)
    else:
        return from_1_2(gpad_line, report=report, group=group, dataset=dataset, bio_entities=bio_entities)
