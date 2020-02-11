from ontobio.io import assocparser
from ontobio.io import entityparser
from ontobio.io import entitywriter
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION, Report
from ontobio.io import qc
from ontobio.model import association

from ontobio.rdfgen import relations
from prefixcommons import curie_util

from typing import List, Dict

import re
import logging

logger = logging.getLogger(__name__)


class GpadParser(assocparser.AssocParser):
    """
    Parser for GO GPAD Format

    https://github.com/geneontology/go-annotation/blob/master/specs/gpad-gpi-1_2.md
    """


    def __init__(self, config=assocparser.AssocParserConfig(), group="unknown", dataset="unknown"):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        self.config = config
        self.report = assocparser.Report(config=self.config, group="unknown", dataset="unknown")
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
            return assocparser.ParseResult(line, [{ "header": True, "line": line.strip() }], False)

        vals = [el.strip() for el in line.split("\t")]

        parsed = to_association(list(vals), report=self.report)
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

        vals = list(go_rule_results.annotation.to_gpad_tsv())
        [db,
         db_object_id,
         qualifier,
         goid,
         reference,
         evidence,
         withfrom,
         interacting_taxon_id,
         date,
         assigned_by,
         annotation_xp,
         annotation_properties] = vals

        split_line = assocparser.SplitLine(line=line, values=vals, taxon="")

        id = self._pair_to_id(db, db_object_id)
        if not self._validate_id(id, split_line, context=ENTITY):
            return assocparser.ParseResult(line, [], True)

        if not self._validate_id(goid, split_line, context=ANNOTATION):
            return assocparser.ParseResult(line, [], True)

        valid_goid = self._validate_ontology_class_id(goid, split_line)
        if valid_goid == None:
            return assocparser.ParseResult(line, [], True)
        goid = valid_goid

        date = self._normalize_gaf_date(date, split_line)

        if reference == "":
            self.report.error(line, Report.INVALID_ID, "EMPTY", "reference column 6 is empty")
            return assocparser.ParseResult(line, [], True)

        self._validate_id(evidence, split_line)

        interacting_taxon = None if interacting_taxon_id == "" else interacting_taxon_id
        if interacting_taxon != None:
            interacting_taxon = self._taxon_id(interacting_taxon_id, split_line)
            if interacting_taxon == None:
                self.report.error(line, assocparser.Report.INVALID_TAXON, interacting_taxon_id,
                                    msg="Taxon ID is invalid")
                return assocparser.ParseResult(line, [], True)

        #TODO: ecomap is currently one-way only
        #ecomap = self.config.ecomap
        #if ecomap != None:
        #    if ecomap.ecoclass_to_coderef(evidence) == (None,None):
        #        self.report.error(line, Report.UNKNOWN_EVIDENCE_CLASS, evidence,
        #                          msg="Expecting a known ECO class ID")

        ## --
        ## qualifier
        ## --
        negated, relation, other_qualifiers = self._parse_qualifier(qualifier, None)


        # Reference Column
        references = self.validate_pipe_separated_ids(reference, split_line)
        if references == None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)

        # With/From
        withfroms = self.validate_pipe_separated_ids(withfrom, split_line, empty_allowed=True, extra_delims=",")
        if withfroms == None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)


        ## --
        ## parse annotation extension
        ## See appending in http://doi.org/10.1186/1471-2105-15-155
        ## --
        object_or_exprs = self._parse_full_extension_expression(annotation_xp, line=split_line)

        subject_symbol = id
        subject_fullname = id
        subject_synonyms = []
        if self.gpi is not None:
            gp = self.gpi.get(id, {})
            if gp is not {}:
                subject_symbol = gp["symbol"]
                subject_fullname = gp["name"]
                subject_synonyms = gp["synonyms"].split("|")

        assoc = {
            'source_line': line,
            'subject': {
                'id': id,
                'label': subject_symbol,
                'fullname': subject_fullname,
                'synonyms': subject_synonyms,
                'taxon': {
                    'id': interacting_taxon
                },
            },
            'object': {
                'id':goid
            },
            'negated': negated,
            'relation': {
                'id': relation
            },
            'interacting_taxon': interacting_taxon,
            'evidence': {
                'type': evidence,
                'with_support_from': withfroms,
                'has_supporting_reference': references
            },
            'subject_extensions': [],
            'object_extensions': {},
            'aspect': self.compute_aspect(goid),
            'provided_by': assigned_by,
            'date': date,
        }
        if len(other_qualifiers) > 0:
            assoc['qualifiers'] = other_qualifiers
        if object_or_exprs is not None and len(object_or_exprs) > 0:
            assoc['object_extensions'] = {'union_of': object_or_exprs}


        return assocparser.ParseResult(line, [assoc], False)

    def is_header(self, line):
        return line.startswith("!")

relation_tuple = re.compile(r'(.+)\((.+)\)')
def to_association(gpad_line: List[str], report=None, group="unknown", dataset="unknown") -> assocparser.ParseResult:

    report = Report(group=group, dataset=dataset) if report is None else report

    source_line = "\t".join(gpad_line)

    if len(gpad_line) > 12:
        report.warning(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were more than 12 columns in this line. Proceeding by cutting off extra columns.",
            rule=1)

        gpad_line = gpad_line[:12]

    if 12 > len(gpad_line) >= 10:
        gpad_line += [""] * (12 - len(gpad_line))

    if len(gpad_line) != 12:
        report.error(source_line, assocparser.Report.WRONG_NUMBER_OF_COLUMNS, "",
            msg="There were {columns} columns found in this line, and there should be between 10 and 12".format(columns=len(gpad_line)))
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

    taxon = ""
    subject_curie = "{db}:{id}".format(db=gpad_line[0], id=gpad_line[1])
    subject = association.Subject(subject_curie, "", "", [], "", "")
    object = association.Term(gpad_line[3], "")
    evidence = association.Evidence(gpad_line[5],
        [e for e in gpad_line[4].split("|") if e],
        [e for e in gpad_line[6].split("|") if e])

    raw_qs = gpad_line[2].split("|")
    negated = "NOT" in raw_qs
    looked_up_qualifiers = [relations.lookup_label(q) for q in raw_qs if q != "NOT"]
    if None in looked_up_qualifiers:
        report.error(source_line, Report.INVALID_QUALIFIER, raw_qs, "Could not find a URI for qualifier", taxon=taxon, rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)


    qualifiers = [curie_util.contract_uri(q)[0] for q in looked_up_qualifiers]

    conjunctions = []
    if gpad_line[11]:
        for conjuncts in gpad_line[11].split("|"):
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

    properties_list = [prop.split("=") for prop in gpad_line[11].split("|") if prop]
    # print(properties_list)
    a = association.GoAssociation(
        source_line="\t".join(gpad_line),
        subject=subject,
        relation="",
        object=object,
        negated=negated,
        qualifiers=qualifiers,
        aspect=None,
        interacting_taxon=gpad_line[7],
        evidence=evidence,
        subject_extensions=[],
        object_extensions=object_extensions,
        provided_by=gpad_line[9],
        date=gpad_line[8],
        properties={ prop[0]: prop[1] for prop in properties_list if prop })

    return assocparser.ParseResult(source_line, [a], False, report=report)
