"""
Parsers for GAF and various Association TSVs.

All parser objects instantiate a subclass of the abstract `AssocParser` object

"""

# TODO: Refactor - move some stuff out into generic parser object

# from _typeshed import NoneType
import re
import requests
import tempfile
from contextlib import closing
import subprocess
import logging
import io
import gzip
import datetime
import dateutil.parser

from dataclasses import dataclass

from collections import namedtuple, defaultdict
from typing import Callable, ClassVar, Collection, Iterable, Optional, List, Dict, Set, TypeVar, Union, Any

from ontobio import ontol
from ontobio import ecomap
from ontobio.io import parsereport
from ontobio.util.user_agent import get_user_agent
from ontobio.model import association
from ontobio.rdfgen import relations

from prefixcommons import curie_util

TAXON = 'TAXON'
ENTITY = 'ENTITY'
ANNOTATION = 'ANNOTATION'
EXTENSION = 'EXTENSION'

logger = logging.getLogger(__name__)


def write_to_file(optional_file, text):
    if optional_file:
        optional_file.write(text)


SplitLine = namedtuple("SplitLine", ["line", "values", "taxon"])
SplitLine.__str__ = lambda self: self.line
"""
This is a collection that views a gaf line in two ways: as the full line, and
as the separated by tab list of values. We also tack on the taxon.
"""

@dataclass
class ValidateResult:
    valid: bool
    original: str
    parsed: Optional[Any]
    message: str

@dataclass
class ColumnValidator:

    def cardinality(self, field: str, entity: str, minimum: int, maximum: Optional[int]) -> ValidateResult:
        items = [i for i in entity.split("|") if i != ""]
        if len(items) == 0 and 0 < minimum:
            return ValidateResult(False, "EMPTY", None, "{} must have at least {} items".format(field, minimum))
        if len(items) < minimum:
            return ValidateResult(False, entity, None, "{} must have at least {} items".format(field, minimum))
        elif maximum is not None and len(items) > maximum:
            return ValidateResult(False, entity, None, "{} cannot have more than {} items".format(field, maximum))

        return ValidateResult(True, entity, items, "")

    def validate(self, entity) -> ValidateResult:
        return ValidateResult(True, entity, entity, "")

@dataclass
class Qualifier2_1(ColumnValidator):
    valid_qualifiers = {
        "contributes_to",
        "colocalizes_with",
    }

    def validate(self, entity) -> ValidateResult:
        result = self.cardinality("Qualifier", entity, 0, 2)
        if not result.valid:
            return result

        invalid_non_not = [q for q in result.parsed if q not in self.valid_qualifiers and q != "NOT"]
        if invalid_non_not:
            result.valid = False
            result.parsed = None
            result.message = "Invalid Qualifiers: {}".format(", ".join(invalid_non_not))

        return result

@dataclass
class Qualifier2_2(ColumnValidator):

    valid_qualifiers = {
        "enables",
        "contributes_to",
        "involved_in",
        "acts_upstream_of",
        "acts_upstream_of_positive_effect",
        "acts_upstream_of_negative_effect",
        "acts_upstream_of_or_within",
        "acts_upstream_of_or_within_positive_effect",
        "acts_upstream_of_or_within_negative_effect",
        "located_in",
        "part_of",
        "is_active_in",
        "colocalizes_with"
    }

    def validate(self, entity) -> ValidateResult:
        result = self.cardinality("Qualifier", entity, 1, 2)
        if not result.valid:
            return result

        invalid_non_not = [q for q in result.parsed if q not in self.valid_qualifiers and q != "NOT"]
        if invalid_non_not:
            result.valid = False
            result.parsed = None
            result.message = "Invalid Qualifiers: {}".format(", ".join(invalid_non_not))
            return result

        if "NOT" in result.parsed and len(result.parsed) == 1:
            # If not is the only elemnent, then it's wrong
            result.valid = False
            result.parsed = None
            result.message = "`NOT` is not a Qualifier and so cannot exist by itself"
            return result

        if len(result.parsed) == 2 and "NOT" not in result.parsed:
            result.valid = False
            result.parsed = None
            result.message = "There can be only one relation entry for the Qualifier field"
            return result

        return result


@dataclass
class CurieValidator(ColumnValidator):
    def validate(self, entity):
        curie = association.Curie.from_str(entity)
        if isinstance(curie, association.Error):
            return ValidateResult(False, entity, None, curie.info)

        return ValidateResult(True, entity, curie, "")


@dataclass
class TaxonValidator(CurieValidator):

    def validate(self, entity):
        cardinality_result = self.cardinality("Taxon", entity, 1, 2)
        if not cardinality_result.valid:
            return cardinality_result

        parsed_taxons = []
        for taxa in cardinality_result.parsed:
            result = super().validate(taxa)
            if not result.valid:
                return result

            result.parsed.namespace = "NCBITaxon"
            parsed_taxons.append(result.parsed)

        return ValidateResult(True, entity, parsed_taxons, "")

@dataclass
class RuleSet:
    """
    This represents the set of GO Rules we want ontobio to run during parsing of annotations.

    If `rules` is None, all rules will be run. If `rules` is an empty set, no rules will be run.
    Otherwise, the rules set member variable is a set of integers corresponding to the rule IDs
    that will be run during parse.

    For example, if self.rules == set([6, 13, 20]) then only GORULE:0000006, GORULE:0000013, and 
    GORULE:0000020 will be run.

    Note that GORULE:0000001 will always be run, as that rule represents succesful parsing a line
    into ontobio at all.
    """
    rules: Optional[Set[int]]

    ALL: ClassVar[str] = "all"

    def __init__(self, rules: Optional[Iterable]):
        if rules is None:
            self.rules = None
        else:
            self.rules = set(rules)
    
    def should_run_rule(self, rule: int) -> bool:
        if self.rules is None:
            return True
        
        return rule in self.rules


class AssocParserConfig():
    """
    Configuration for an association parser

    rule_metadata: Dictionary of rule IDs to metadata pulled out by yamldown

    rule_sets: an Iterable of integers representing 
    """
    def __init__(self,
                 remove_double_prefixes=False,
                 ontology=None,
                 repair_obsoletes=True,
                 entity_map=None,
                 valid_taxa=None,
                 class_idspaces=None,
                 entity_idspaces=None,
                 group_idspace=None,
                 ecomap=ecomap.EcoMap(),
                 exclude_relations=None,
                 include_relations=None,
                 filter_out_evidence=None,
                 filtered_evidence_file=None,
                 gpi_authority_path=None,
                 paint=False,
                 rule_metadata=dict(),
                 goref_metadata=None,
                 group_metadata=None,
                 dbxrefs=None,
                 suppress_rule_reporting_tags=[],
                 annotation_inferences=None,
                 extensions_constraints=None,
                 rule_contexts=[],
                 rule_set=None):

        self.remove_double_prefixes=remove_double_prefixes
        self.ontology=ontology
        self.repair_obsoletes=repair_obsoletes
        self.entity_map=entity_map
        self.valid_taxa=valid_taxa
        self.class_idspaces=class_idspaces
        self.ecomap=ecomap
        self.include_relations=include_relations
        self.exclude_relations=exclude_relations
        self.filter_out_evidence = filter_out_evidence
        self.filtered_evidence_file = filtered_evidence_file
        self.gpi_authority_path = gpi_authority_path
        self.paint = paint
        self.rule_metadata = rule_metadata
        self.goref_metadata = goref_metadata
        self.group_metadata = group_metadata
        self.suppress_rule_reporting_tags = suppress_rule_reporting_tags
        self.annotation_inferences = annotation_inferences
        self.entity_idspaces = entity_idspaces
        self.extensions_constraints = AssocParserConfig._compute_constraint_subclasses(extensions_constraints, ontology)
        self.group_idspace = None if group_idspace is None else set(group_idspace)
        self.rule_contexts = rule_contexts
        # We'll say that the default None should run no rules, so let's set the rule_set to []
        # print("Rule Set is {}".format(rule_set))
        if rule_set == None:
            self.rule_set = RuleSet([])
        elif rule_set == RuleSet.ALL:
            # None here means all rules
            self.rule_set = RuleSet(None)
        else:
            self.rule_set = RuleSet(rule_set)


        # This is a dictionary from ruleid: `gorule-0000001` to title strings
        if self.exclude_relations is None:
            self.exclude_relations = []
        if self.include_relations is None:
            self.include_relations = []
        if self.filter_out_evidence is None:
            self.filter_out_evidence = []


    def _compute_constraint_subclasses(extensions_constraints, ontology):
        if extensions_constraints is None:
            return None
        # Precompute subclass closures in the extensions_constraints
        cache = dict()  # term -> [children]
        for constraint in extensions_constraints:
            terms = set()
            for term in constraint["primary_root_terms"]:
                if not term in cache and ontology is not None:
                    cache[term] = ontology.descendants(term, relations=["subClassOf"], reflexive=True)
                elif ontology is None:
                    cache[term] = [term]

                terms.update(cache[term])

            constraint["primary_terms"] = sorted(list(terms))

        return extensions_constraints

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    def __str__(self):
        s = "AssocParserConfig("
        attribute_values = ["{att}={val}".format(att=att, val=dict([(k, v) for k, v in value.items()][:8]) if isinstance(value, dict) else value) for att, value in vars(self).items()]
        return "AssocParserConfig({})".format(",".join(attribute_values))

class Report(object):
    """
    A report object that is generated as a result of a parse
    """

    # Levels
    """
    4  message levels
    """
    FATAL = 'FATAL'
    ERROR = 'ERROR'
    WARNING = 'WARNING'
    INFO = "INFO"

    # Warnings: TODO link to gorules
    INVALID_ID = "Invalid identifier"
    INVALID_ID_DBXREF = "ID or symbol not present in DB xrefs file"
    UNKNOWN_ID = "Unknown identifier"
    INVALID_IDSPACE = "Invalid identifier prefix"
    INVALID_QUALIFIER = "Invalid Qualifier"
    INVALID_TAXON = "Invalid taxon"
    INVALID_SYMBOL = "Invalid symbol"
    INVALID_DATE = "Invalid date"
    INVALID_ASPECT = "Invalid aspect code. Should be C, P, or F"
    UNMAPPED_ID = "Unmapped identifier"
    UNKNOWN_EVIDENCE_CLASS = "Unknown evidence class"
    OBSOLETE_CLASS = "Obsolete class"
    OBSOLETE_CLASS_NO_REPLACEMENT = "Obsolete class with no replacement"
    WRONG_NUMBER_OF_COLUMNS = "Wrong number of columns in this line"
    EXTENSION_SYNTAX_ERROR = "Syntax error in annotation extension field"
    VIOLATES_GO_RULE = "Violates GO Rule"
    RULE_PASS = "Passes GO Rule"
    INVALID_REFERENCES = "Only one reference per ID space allowed"


    def __init__(self, group="unknown", dataset="unknown", config=None):
        self.messages = []
        self.n_lines = 0
        self.n_assocs = 0
        self.skipped = 0
        self.reporter = parsereport.Report(group, dataset)
        if config is None:
            config = AssocParserConfig()
        self.config = config
        self.header = []

    def error(self, line, type, obj, msg="", taxon: str = "", rule=None):
        self.message(self.ERROR, line, type, obj, msg, taxon=taxon, rule=rule)

    def warning(self, line, type, obj, msg="", taxon: str = "", rule=None):
        self.message(self.WARNING, line, type, obj, msg, taxon=taxon, rule=rule)

    def message(self, level, line, type, obj, msg="", taxon: str = "", rule=None, dont_record=["INFO"]):
        message = {
            'level': level,
            'line': line,
            'type': type,
            'message': msg,
            'obj': obj,
            'taxon': taxon,
            'rule': rule
        }
        if not level in dont_record:
            # Only record a message if we want that
            self.messages.append(message)

        self.reporter.message(message, rule)

    def add_associations(self, associations):
        for a in associations:
            self.add_association(a)

    def add_association(self, association):
        if isinstance(association, dict) and "header" in association:
            # Then we are a header
            self.header.append(association["line"])
        else:
            self.n_assocs += 1
        # self.subjects.add(association['subject']['id'])
        # self.objects.add(association['object']['id'])
        # self.references.update(association['evidence']['has_supporting_reference'])
        # if 'taxon' in association['subject']:
        #     self.taxa.add(association['subject']['taxon']['id'])

    def report_parsed_result(self, result, output_file, evidence_filtered_file, evidence_to_filter):

        self.n_lines += 1
        if result.skipped:
            logger.debug("SKIPPING (assocparser): {}".format(result.parsed_line))
            self.skipped += 1
        else:
            self.add_associations(result.associations)
            if result.evidence_used not in evidence_to_filter:
                write_to_file(evidence_filtered_file, result.parsed_line + "\n")

    def short_summary(self):
        return "Parsed {} assocs from {} lines. Skipped: {}".format(self.n_assocs, self.n_lines, self.skipped)

    def to_report_json(self):
        """
        Generate a summary in json format
        """

        return self.reporter.json(self.n_lines, self.n_assocs, self.skipped)

    def to_markdown(self):
        """
        Generate a summary in markdown format
        """
        json = self.to_report_json()
        # summary = json['summary']

        s = "# Group: {group} - Dataset: {dataset}\n".format(group=json["group"], dataset=json["dataset"])
        s += "\n## SUMMARY\n\n"
        s += "This report generated on {}\n\n".format(datetime.date.today())
        s += "  * Associations: {}\n" . format(json["associations"])
        s += "  * Lines in file (incl headers): {}\n" . format(json["lines"])
        s += "  * Lines skipped: {}\n" . format(json["skipped_lines"])
        # Header from GAF
        s += "## Header From Original Association File\n\n"
        s += "\n".join(["> {}  ".format(head) for head in self.header])
        ## Table of Contents
        s += "\n\n## Contents\n\n"
        for rule, messages in sorted(json["messages"].items(), key=lambda t: t[0]):
            any_suppress_tag_in_rule_metadata = any([tag in self.config.rule_metadata.get(rule, {}).get("tags", []) for tag in self.config.suppress_rule_reporting_tags])
            # For each tag we say to suppress output for, check if it matches any tag in the rule. If any matches
            if self.config.rule_metadata and any_suppress_tag_in_rule_metadata:
                print("Skipping {rule_num} because the tag(s) '{tag}' are suppressed".format(rule_num=rule, tag=", ".join(self.config.suppress_rule_reporting_tags)))
                continue

            s += "[{rule}](#{rule})\n\n".format(rule=rule)

        s += "\n## MESSAGES\n\n"
        for (rule, messages) in sorted(json["messages"].items(), key=lambda t: t[0]):
            any_suppress_tag_in_rule_metadata = any([tag in self.config.rule_metadata.get(rule, {}).get("tags", []) for tag in self.config.suppress_rule_reporting_tags])

            # Skip if the rule metadata has "silent" as a tag
            if self.config.rule_metadata and any_suppress_tag_in_rule_metadata:
                # If there is a rule metadata, and the rule ID is in the config,
                # get the list of tags if present and check for existence of "silent".
                # If contained, continue to the next rule.
                continue


            s += "### {rule}\n\n".format(rule=rule)
            if rule != "other" and self.config.rule_metadata:
                s += "{title}\n\n".format(title=self.config.rule_metadata.get(rule, {}).get("title", ""))
            s += "* total: {amount}\n".format(amount=len(messages))
            if len(messages) > 0:
                s += "#### Messages\n"
            for message in messages:
                obj = " ({})".format(message["obj"]) if message["obj"] else ""
                s += "* {level} - {type}: {message}{obj} -- `{line}`\n".format(level=message["level"], type=message["type"], message=message["message"], line=message["line"], obj=obj)

        return s

@dataclass
class ParseResult:
    parsed_line: str
    associations: List[association.GoAssociation]
    skipped: bool
    report: Optional[Report] = None
    evidence_used: List[str] = None


# TODO avoid using names that are builtin python: file, id

class AssocParser(object):
    """
    Abstract superclass of all association parser classes
    """
    def is_header(self, line):
        return line.startswith("!")

    def parse(self, file, skipheader=False, outfile=None):
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
        associations = self.association_generator(file, skipheader=skipheader, outfile=outfile)
        a = list(associations)
        return a

    def association_generator(self, file, skipheader=False, outfile=None) -> Dict:
        """
        Returns a generator that yields successive associations from file

        Yields
        ------
        association
        """
        file = self._ensure_file(file)
        for line in file:
            parsed_result = self.parse_line(line)
            self.report.report_parsed_result(parsed_result, outfile, self.config.filtered_evidence_file, self.config.filter_out_evidence)
            for association in parsed_result.associations:
                # yield association if we don't care if it's a header or if it's definitely a real gaf line
                if not skipheader or not isinstance(association, dict):
                    yield association

        logger.info(self.report.short_summary())
        file.close()

    def generate_associations(self, line, outfile=None):
        associations = self.association_generator(line, outfile=outfile)
        for association in associations:
            pass

    def validate_line(self, line):
        if line == "":
            self.report.warning(line, Report.WRONG_NUMBER_OF_COLUMNS, "",
                                msg="GORULE:0000001: empty line", rule=1)
            return ParseResult(line, [], True)

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
            logger.info("Creating mapping for subset: {}".format(subset))
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
            logger.debug("LINE: {} VALS: {}".format(line, vals))
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

    def normalize_columns(self, number_of_columns, columns):
        columns += [""] * (number_of_columns - len(columns))
        return columns

    # def parse_line(self, line) -> ParseResult:
    #     if self.is_header(line):
    #         # Then do a thing with the header?
    #         return ParseResult(line, [HeaderLine(line)], False)
    #
    #     tsv_line = line.split("\t")
    #     self.parse_to_association(tsv_line)


    def _skipping_line(self, associations):
        return associations is None or associations == []

    def _is_exclude_relation(self, relation):
        if self.config.include_relations is not None and len(self.config.include_relations) > 0:
            if relation not in self.config.include_relations:
                return True
        if self.config.exclude_relations is not None and len(self.config.exclude_relations) > 0:
            if relation in self.config.exclude_relations:
                return True
        return False

    def compute_aspect(self, term):
        if self.config.ontology == None:
            return None

        BP = "GO:0008150"
        CC = "GO:0005575"
        MF = "GO:0003674"

        ancestors = self.config.ontology.ancestors(term)
        if BP in ancestors:
            return "P"
        if CC in ancestors:
            return "C"
        if MF in ancestors:
            return "F"

        return None

    ## we generate both qualifier and relation field
    ## Returns: (negated, relation, other_qualifiers)
    def _parse_qualifier(self, qualifier, aspect):
        return _parse_qualifier(qualifier, aspect)

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

    def _validate_taxon(self, taxon, line: SplitLine):
        if self.config.valid_taxa is None:
            return True
        else:
            if taxon in self.config.valid_taxa:
                return True
            else:
                self.report.error(line.line, Report.INVALID_TAXON, taxon, taxon=taxon)
                return False

    # check the term id is in the ontology, and is not obsolete
    def _validate_ontology_class_id(self, id, line: SplitLine, subclassof=None):
        ont = self.config.ontology
        if ont is None:
            return id

        if not ont.has_node(id):
            self.report.warning(line.line, Report.UNKNOWN_ID, id, "Class ID {} is not present in the ontology".format(id),
                taxon=line.taxon, rule=27)
            return id

        if ont.is_obsolete(id):
            # the default behavior should always be to repair, unless the caller explicitly states
            # that this should not be done by setting repair_obsoletes to False
            if self.config.repair_obsoletes is None or self.config.repair_obsoletes:
                rb = ont.replaced_by(id, strict=False)
                if len(rb) == 1:
                    # We can repair
                    self.report.warning(line.line, Report.OBSOLETE_CLASS, id, msg="Violates GORULE:0000020, but was repaired",
                        taxon=line.taxon, rule=20)
                    id = rb[0]
                else:
                    self.report.warning(line.line, Report.OBSOLETE_CLASS_NO_REPLACEMENT, id, msg="Violates GORULE:0000020",
                        taxon=line.taxon, rule=20)
                    id = None
            else:
                self.report.warning(line.line, Report.OBSOLETE_CLASS, id, msg="Violates GORULE:0000020",
                    taxon=line.taxon, rule=20)
                id = None

        return id

    def _validate_symbol(self, symbol, line: SplitLine):
        if symbol is None or symbol == "":
            self.report.warning(line.line, Report.INVALID_SYMBOL, symbol, "GORULE:0000027: symbol is empty",
                taxon=line.taxon, rule=27)

    non_id_regex = re.compile(r"[^\.:_\-0-9a-zA-Z]")
    doi_regex = re.compile(r"^doi:", flags=re.IGNORECASE)

    def _validate_id(self, id, line: SplitLine, allowed_ids=None, context=None):

        # we assume that cardinality>1 fields have been split prior to this

        if id == "":
            self.report.error(line.line, Report.INVALID_ID, id, "GORULE:0000027: identifier is empty", taxon=line.taxon, rule=27)
            return False
        if ':' not in id:
            self.report.error(line.line, Report.INVALID_ID, id, "GORULE:0000027: must be CURIE/prefixed ID", rule=27)
            return False

        # we won't check IDs with doi prefix, everything else we want to check
        if not AssocParser.doi_regex.match(id) and AssocParser.non_id_regex.search(id):
            self.report.error(line.line, Report.INVALID_ID, id, "GORULE:0000027: contains non letter, non number character, or spaces", rule=27)
            return False

        (id_prefix, right) = id.split(":", maxsplit=1)
        if right.startswith("MGI:"):
            ## See ticket https://github.com/geneontology/go-site/issues/91
            ## For purposes of determining allowed IDs in DB XREF, MGI IDs shall look like `MGI:12345`
            right = right[4:]

        if id_prefix == "" or right == "":
            self.report.error(line.line, Report.INVALID_ID, id, "GORULE:0000027: Empty ID", rule=27)
            return False

        if allowed_ids is not None and id_prefix not in allowed_ids:
            # For now we will just issue a warning here, and we won't filter out the annotation here
            self.report.warning(line.line, Report.INVALID_ID_DBXREF, id_prefix, "allowed: {}".format(allowed_ids), rule=27)

        # ensure that the ID space of the annotation class (e.g. GO)
        # conforms to what is expected
        if context == ANNOTATION and self.config.class_idspaces is not None:
            if id_prefix not in self.config.class_idspaces:
                self.report.error(line.line, Report.INVALID_IDSPACE, id_prefix, "allowed: {}".format(self.config.class_idspaces), rule=27)
                return False

        return True

    def validate_pipe_separated_ids(self, column, line: SplitLine, empty_allowed=False, extra_delims="") -> Optional[List[str]]:
        if column == "" and empty_allowed:
            return []

        split_ids = re.split("[|{}]".format(extra_delims), column)
        valids = []
        for i in split_ids:
            if self._validate_id(i, line):
                valids.append(i)
            else:
                return None

        return sorted(valids)

    def validate_curie_ids(self, ids: List[association.Curie], line: SplitLine) -> Optional[List[association.Curie]]:
        valids = []
        for i in ids:
            if self._validate_id(str(i), line):
                valids.append(i)
            else:
                return None

        return valids

        # We are only reporting, so just pass it through

    def _normalize_id(self, id):
        toks = id.split(":")
        if len(toks) > 1:
            return self._pair_to_id(toks[0], ":".join(toks[1:]))
        else:
            return id

    def _pair_to_id(self, db, localid):
        if self.config.remove_double_prefixes:
            ## Switch MGI:MGI:n to MGI:n
            if localid.startswith(db+":"):
                localid = localid.replace(db+":", "")
        return db + ":" + localid

    def _taxon_id(self, id, line: SplitLine):
        id = id.replace('taxon', 'NCBITaxon')
        valid = self._validate_id(id, line, context=TAXON)
        if valid:
            return id
        else:
            return None

    def _ensure_file(self, file):
        logger.info("Ensure file: {}".format(file))
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
                with closing(requests.get(url, stream=False, headers={'User-Agent': get_user_agent(modules=[requests], caller_name=__name__)})) as resp:
                    logger.info("URL: {} STATUS: {} ".format(url, resp.status_code))
                    ok = resp.status_code == 200
                    if ok:
                        logger.debug("HEADER: {}".format(resp.headers))
                        if file.endswith(".gz"):
                            return io.StringIO(str(gzip.decompress(resp.content),'utf-8'))
                        else:
                            out = io.StringIO(resp.content)
                            return out
                    else:
                        return None
            else:
                logger.info("Testing suffix of {}".format(file))
                if file.endswith(".gz"):
                    return gzip.open(file, "rt")
                else:
                    return open(file, "r")
        else:
            return file

    def _parse_full_extension_expression(self, xp, line: SplitLine = None):
        if xp == "":
            return None

        object_or_exprs = []
        xp_ors = sorted(xp.split("|"))
        for xp_or in xp_ors:

            # gather conjunctive expressions in extensions field
            xp_ands = sorted(xp_or.split(","))
            and_exprs = []
            for xp_and in xp_ands:
                if xp_and != "":
                    expr = self._parse_relationship_expression(xp_and, line=line)
                    if expr is not None:
                        and_exprs.append(expr)
            if len(and_exprs) > 0:
                object_or_exprs.append({'intersection_of': and_exprs})
        return object_or_exprs


    relation_tuple = re.compile(r'(.+)\((.+)\)')
    def _parse_relationship_expression(self, x, line: SplitLine = None):
        ## Parses an atomic relational expression
        ## E.g. exists_during(GO:0000753)
        ## Atomic class expressions only
        tuples = AssocParser.relation_tuple.findall(x)
        if len(tuples) != 1:
            self.report.error(line.line, Report.EXTENSION_SYNTAX_ERROR, x, msg="does not follow REL(ID) syntax")
            return None
        (p, v) = tuples[0]

        if self._validate_id(v, line, context=EXTENSION):
            return {
                'property': p,
                'filler': v
            }
        else:
            self.report.error(line.line, Report.EXTENSION_SYNTAX_ERROR, x, msg="GORULE:0000027: ID not valid", rule=27)
            return None



def parse_date(date: str, report: Report, line: List) -> Optional[association.Date]:
    if date == "":
        report.error(line, Report.INVALID_DATE, "\'\'", "GORULE:0000001: empty", rule=1)
        return None

    d = None
    if len(date) == 8 and date.isdigit():
        # For GAF date, should be YYYYMMDD all as digits and
        # a well formed date string here will be exactly 8 characters long
        d = association.Date(year=date[0:4], month=date[4:6], day=date[6:8], time="")
    else:
        report.warning(line, report.INVALID_DATE, date, "GORULE:0000001: Date field must be YYYYMMDD, got: {}".format(date), rule=1)
        parsed = None
        try:
            parsed = dateutil.parser.parse(date)
        except:
            report.error(line, Report.INVALID_DATE, date, "GORULE:0000001: Could not parse date '{}' at all".format(date), rule=1)
            return None

        d = association.Date(year="{:02d}".format(parsed.year), month="{:02d}".format(parsed.month), day="{:02d}".format(parsed.day), time="")

    return d

def parse_iso_date(date: str, report: Report, line: List) -> Optional[association.Date]:

    def parse_with_dateutil(date: str, repot: Report, line: List) -> Optional[association.Date]:
        parsed = None
        try:
            parsed = dateutil.parser.parse(date)
        except:
            report.error(line, Report.INVALID_DATE, date, "GORULE:0000001: Could not parse date '{}' at all".format(date), rule=1)
            return None

        return association.Date(
            year="{:02d}".format(parsed.year),
            month="{:02d}".format(parsed.month),
            day="{:02d}".format(parsed.day),
            time=parsed.time().isoformat())


    if date == "":
        report.error(line, Report.INVALID_DATE, "\'\'", "GORULE:0000001: empty", rule=1)
        return None

    d = None
    if len(date) >= 10:
        # For ISO style date, should be YYYY-MM-DD all as digits and
        # a well formed date string here will be at least 10 characters long.
        # Optionally, there could be an appended THH:MM
        year = date[0:4]
        month = date[5:7]
        day = date[8:10]
        time = date[11:]
        if year.isdigit() and month.isdigit() and day.isdigit():
            d = association.Date(year=year, month=month, day=day, time=time)
        else:
            # If any of year, month, day are not made of digits, then try to parse with dateutil
            report.warning(line, report.INVALID_DATE, date, "GORULE:0000001: Date field must be YYYY-MM-DD, got: {}".format(date), rule=1)
            d = parse_with_dateutil(date, report, line)

    else:
        # If we got the wrong number characters in the date, then fallback to dateutil
        report.warning(line, report.INVALID_DATE, date, "GORULE:0000001: Date field must be YYYY-MM-DD, got: {}".format(date), rule=1)
        d = parse_with_dateutil(date, report, line)

    return d


## we generate both qualifier and relation field
## Returns: (negated, relation, other_qualifiers)
def _parse_qualifier(qualifier, aspect):
    relation = None
    qualifiers = qualifier.split("|")
    if qualifier == '':
        qualifiers = []
    negated = 'NOT' in qualifiers
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

# TODO consider making an Association its own class too to give it a little more
# TODO Semantic value?

# TODO consider making an ID class?
