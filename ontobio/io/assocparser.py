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
import gzip
import datetime
import dateutil.parser

from typing import Optional, List

from ontobio import ontol
from ontobio import ecomap
from ontobio.util.user_agent import get_user_agent

TAXON = 'TAXON'
ENTITY = 'ENTITY'
ANNOTATION = 'ANNOTATION'
EXTENSION = 'EXTENSION'


def write_to_file(optional_file, text):
    if optional_file:
        optional_file.write(text)


class ParseResult(object):

    def __init__(self, parsed_line, associations, skipped, evidence_used=None):
        self.parsed_line = parsed_line
        self.associations = associations
        self.skipped = skipped
        self.evidence_used = evidence_used


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
                 ecomap=ecomap.EcoMap(),
                 exclude_relations=None,
                 include_relations=None,
                 filter_out_evidence=None,
                 filtered_evidence_file=None,
                 gpi_authority_path=None,
                 paint=False):

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
        if self.exclude_relations is None:
            self.exclude_relations = []
        if self.include_relations is None:
            self.include_relations = []
        if self.filter_out_evidence is None:
            self.filter_out_evidence = []


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
        self.max_messages = 10000

    def error(self, line, type, obj, msg=""):
        self.message(self.ERROR, line, type, obj, msg)
    def warning(self, line, type, obj, msg=""):
        self.message(self.WARNING, line, type, obj, msg)
    def message(self, level, line, type, obj, msg=""):
        # Only keep max_messages number of messages
        if len(self.messages) > self.max_messages:
            # TODO: ensure the message is captured if we are streaming
            return
        self.messages.append({'level':level,
                              'line':line,
                              'type':type,
                              'message':msg,
                              'obj':obj})


    def add_associations(self, associations):
        for a in associations:
            self.add_association(a)

    def add_association(self, association):
        self.n_assocs += 1
        # self.subjects.add(association['subject']['id'])
        # self.objects.add(association['object']['id'])
        # self.references.update(association['evidence']['has_supporting_reference'])
        # if 'taxon' in association['subject']:
        #     self.taxa.add(association['subject']['taxon']['id'])

    def report_parsed_result(self, result, output_file, evidence_filtered_file, evidence_to_filter):

        self.n_lines += 1
        if result.skipped:
            logging.info("SKIPPING: {}".format(result.parsed_line))
            self.skipped.append(result.parsed_line)
        else:
            self.add_associations(result.associations)
            if result.evidence_used not in evidence_to_filter:
                write_to_file(evidence_filtered_file, result.parsed_line + "\n")

    def short_summary(self):
        return "Parsed {} assocs from {} lines. Skipped: {}".format(self.n_assocs, self.n_lines, len(self.skipped))

    def to_report_json(self):
        """
        Generate a summary in json format
        """

        N = 10
        report = {
            "summary": {
                "association_count": self.n_assocs,
                "line_count": self.n_lines,
                "skipped_line_count": len(self.skipped)
            },
            "aggregate_statistics": {
                "subject_count": len(self.subjects),
                "object_count": len(self.objects),
                "taxon_count": len(self.taxa),
                "reference_count": len(self.references),
                "taxon_sample": list(self.taxa)[0:N],
                "subject_sample": list(self.subjects)[0:N],
                "object_sample": list(self.objects)[0:N]
            }
        }

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
            mgroup = {
                "level": level,
                "count": len(msgs),
                "messages": msgs
            }
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

class AssocParser(object):
    """
    Abstract superclass of all association parser classes
    """

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

    def association_generator(self, file, skipheader=False, outfile=None):
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
                if not skipheader or "header" not in association:
                    yield association

        logging.info(self.report.short_summary())
        file.close()

    def generate_associations(self, line, outfile=None):
        associations = self.association_generator(line, outfile=outfile)
        for association in associations:
            pass

    def validate_line(self, line):
        if line == "":
            self.report.warning(line, Report.WRONG_NUMBER_OF_COLUMNS, "",
                                msg="empty line")
            return ParseResult(line, [], True)

    def _validate_assoc(self, assoc, line):
        """
        Performs validation on an ontology association structure.

        Currently the only validation is checking the ontology class (object) id against the loaded ontology
        """
        self._validate_ontology_class_id(assoc["object"]["id"], line)

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
            # the default behavior should always be to repair, unless the caller explicitly states
            # that this should not be done by setting repair_obsoletes to False
            if self.config.repair_obsoletes is None or self.config.repair_obsoletes:
                rb = ont.replaced_by(id, strict=False)
                if len(rb) == 1:
                    self.report.warning(line, Report.OBSOLETE_CLASS, id)
                    id = rb[0]
                else:
                    self.report.warning(line, Report.OBSOLETE_CLASS_NO_REPLACEMENT, id)
            else:
                self.report.warning(line, Report.OBSOLETE_CLASS, id)
        # TODO: subclassof
        return id

    def _normalize_gaf_date(self, date, line):
        if date is None or date == "":
            self.report.warning(line, Report.INVALID_DATE, date, "empty")
            return date

        # We check int(date)
        if len(date) == 8 and date.isdigit():
            d = datetime.datetime(int(date[0:4]), int(date[4:6]), int(date[6:8]), 0, 0, 0, 0)
        else:
            self.report.warning(line, Report.INVALID_DATE, date, "Date field must be YYYYMMDD, got: {}".format(date))
            try:
                d = dateutil.parser.parse(date)
            except:
                self.report.error(line, Report.INVALID_DATE, date, "Could not parse date '{}' at all".format(date))
                return date

        return d.strftime("%Y%m%d")

    def _validate_symbol(self, symbol, line):
        if symbol is None or symbol == "":
            self.report.warning(line, Report.INVALID_SYMBOL, symbol, "empty")

    non_id_regex = re.compile("[^\.:_\-0-9a-zA-Z]")

    def _validate_id(self, id, line, context=None):

        # we assume that cardinality>1 fields have been split prior to this
        if id.find("|") > -1:
            # non-fatal
            self.report.warning(line, Report.INVALID_ID, id, "contains pipe in identifier")
        if ':' not in id:
            self.report.error(line, Report.INVALID_ID, id, "must be CURIE/prefixed ID")
            return False

        if AssocParser.non_id_regex.search(id.split(":")[1]):
            self.report.error(line, Report.INVALID_ID, id, "contains non letter, non number character, or spaces")
            return False

        (left, right) = id.rsplit(":", maxsplit=1)
        if len(left) == 0 or len(right) == 0:
            self.report.error(line, Report.INVALID_ID, id, "Empty ID")
            return False

        idspace = self._get_id_prefix(id)
        # ensure that the ID space of the annotation class (e.g. GO)
        # conforms to what is expected
        if context == ANNOTATION and self.config.class_idspaces is not None:
            if idspace not in self.config.class_idspaces:
                self.report.error(line, Report.INVALID_IDSPACE, id, "allowed: {}".format(self.config.class_idspaces))
                return False

        return True

    def validate_pipe_separated_ids(self, column, line, empty_allowed=False, extra_delims="") -> Optional[List[str]]:
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
                localid = localid.replace(db+":","")
        return db + ":" + localid

    def _taxon_id(self, id):
        id = id.replace('taxon', 'NCBITaxon')
        valid = self._validate_id(id, '', TAXON)
        if valid:
            return id
        else:
            return None

    def _ensure_file(self, file):
        logging.info("Ensure file: {}".format(file))
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
                    logging.info("URL: {} STATUS: {} ".format(url, resp.status_code))
                    ok = resp.status_code == 200
                    if ok:
                        logging.debug("HEADER: {}".format(resp.headers))
                        if file.endswith(".gz"):
                            return io.StringIO(str(gzip.decompress(resp.content),'utf-8'))
                        else:
                            out = io.StringIO(resp.content)
                            return out
                    else:
                        return None
            else:
                logging.info("Testing suffix of {}".format(file))
                if file.endswith(".gz"):
                    return gzip.open(file, "rt")
                else:
                    return open(file, "r")
        else:
            return file

    def _parse_full_extension_expression(self, xp, line=""):
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
                object_or_exprs.append({'intersection_of':and_exprs})
        return object_or_exprs


    relation_tuple = re.compile('(.*)\((.*)\)')
    def _parse_relationship_expression(self, x, line=""):
        ## Parses an atomic relational expression
        ## E.g. exists_during(GO:0000753)
        ## Atomic class expressions only
        tuples = AssocParser.relation_tuple.findall(x)
        if len(tuples) != 1:
            self.report.error(line, Report.EXTENSION_SYNTAX_ERROR, x, msg="does not follow REL(ID) syntax")
            return None
        (p,v) = tuples[0]

        if self._validate_id(v, line,EXTENSION):
            return {
                'property':p,
                'filler':v
            }
        else:
            self.report.error(line, Report.EXTENSION_SYNTAX_ERROR, x, msg="ID not valid")
            return None

# TODO consider making an Association its own class too to give it a little more
# TODO Semantic value?

# TODO consider making an ID class?
