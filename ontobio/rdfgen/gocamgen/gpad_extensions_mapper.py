# from ontobio.io.gafparser import GafParser
from ontobio.io.gpadparser import GpadParser
from ontobio.io.assocparser import SplitLine
from ontobio.ontol_factory import OntologyFactory
# from prefixcommons import curie_util
from ontobio.ecomap import EcoMap
from ontobio.util.go_utils import GoAspector
from ontobio.rdfgen.assoc_rdfgen import prefix_context
from .filter_rule import *
from .collapsed_assoc import extract_properties
import json
import csv
import os
import argparse
import logging
import datetime
from pathlib import Path


DISTINCT_EXTENSIONS = {}

# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.setLevel("INFO")

parser = argparse.ArgumentParser()
parser.add_argument("-f", "--filename")
parser.add_argument("-d", "--dir")
parser.add_argument("-c", "--constraints_yaml")
parser.add_argument("-o", "--out_file")
parser.add_argument("-l", "--leftovers_out_file")
parser.add_argument("-p", "--pattern")
parser.add_argument("-q", "--pattern_outfile")
parser.add_argument("-r", "--pattern_sourcefile")
parser.add_argument("-m", "--mod")
parser.add_argument("-e", "--extensions_list", action='store_const', const=True,
                    help="Print out distinct extensions list")

ontology_prefixes = []
for k, v in prefix_context.items():
    if v.startswith("http://purl.obolibrary.org/obo/"):
        ontology_prefixes.append(k)
ontology_prefixes.append("Pfam")

mod_prefixes = [
    "PomBase",
    "UniProtKB",
]

acceptable_evidence_codes = [
    "EXP",
    "IDA",
    "IPI",
    "IMP",
    "IGI",
    "IEP"
]
ecomap = EcoMap()


def date_fname(fname):
    date_str = datetime.date.today().isoformat()
    fname_and_ext = os.path.splitext(fname)
    new_fname = fname_and_ext[0]
    new_fname += "_{}".format(date_str.replace("-", ""))
    new_fname += fname_and_ext[1]
    return new_fname

class ExtRelationPattern:
    def __init__(self, ext_relation, ext_namespaces, primary_term_roots=None, max_allowed=None):
        self.ext_relation = ext_relation
        self.ext_namespaces = ext_namespaces
        self.max_allowed = max_allowed  # cardinality?
        self.primary_term_roots = primary_term_roots if isinstance(primary_term_roots, list) else [primary_term_roots]
        # TODO: Also handle primary_term_roots == None


class ExtRelationValidPattern(ExtRelationPattern):
    def __init__(self, ext_relation, ext_namespaces, primary_term_roots=None, max_allowed=None):
        ExtRelationPattern.__init__(self, ext_relation, ext_namespaces, primary_term_roots, max_allowed)
        self.is_valid = True


class ExtRelationInvalidPattern(ExtRelationPattern):
    def __init__(self, ext_relation, ext_namespaces, primary_term_roots=None, max_allowed=None):
        ExtRelationPattern.__init__(self, ext_relation, ext_namespaces, primary_term_roots, max_allowed)
        self.is_valid = False


# Extension rules - These should live in separate files
FUNCTION_SINGLES_ONLY = [
    "occurs_in(GO:C)",
    "occurs_in(CL)",
    "occurs_in(UBERON)",
    "occurs_in(EMAPA)",
    "has_input(geneID)",
    "has_input(CHEBI)",
    "has_direct_input(geneID)",
    "has_direct_input(CHEBI)",
    "happens_during(GO:P)",
    "part_of(GO:P)",
    "has_regulation_target(geneID)",
    "activated_by(CHEBI)",
    "inhibited_by(CHEBI)"
]
COMPONENT_SINGLES_ONLY = [
    "part_of(GO:C)",
    "part_of(CL)",
    "part_of(UBERON)",
    "part_of(EMAPA)"
]
PROCESS_SINGLES_ONLY = [
    "occurs_in(GO:C)",
    "occurs_in(CL)",
    "occurs_in(UBERON)",
    "occurs_in(EMAPA)",
    "occurs_in(WBbt)",
    "has_input(geneID)",
    "has_input(CHEBI)",
    "has_direct_input(geneID)",
    "has_direct_input(CHEBI)",
    "has_regulation_target(geneID)",
    "part_of(GO:P)"
]
EXTENSION_RELATION_UNIVERSE = []  # Should this also be aspect-specific?
for r in FUNCTION_SINGLES_ONLY + COMPONENT_SINGLES_ONLY + PROCESS_SINGLES_ONLY:
    if r not in EXTENSION_RELATION_UNIVERSE:
        EXTENSION_RELATION_UNIVERSE.append(r)
# Add remaining extensions not having cardinality restrictions yet we know how to translate them
EXTENSION_RELATION_UNIVERSE.append([
    "has_regulation_target(geneID)"
])


gaf_indices = {}
gpad_indices = {

}

# TODO: Check where Aspector is used in gocamgen. If only for validating extensions we may be able to remove it.
class CachedGoAspector(GoAspector):

    def __init__(self, cache_filepath=None, go_ontology=None):
        GoAspector.__init__(self, go_ontology)
        if cache_filepath is None:
            # TODO: Where to store cache?
            cache_filepath = "resources/aspect_lookup.json"
        self.cache_filepath = cache_filepath
        self.aspect_lookup = {
            "F": [],
            "P": [],
            "C": []
        }
        aspect_file = Path(self.cache_filepath)
        if not aspect_file.is_file():
            logger.debug("Creating aspect_lookup cache file: {}".format(self.cache_filepath))
            self.write_cache()
        else:
            with open(cache_filepath) as af:
                try:
                    self.aspect_lookup = json.load(af)
                except json.decoder.JSONDecodeError:
                    logger.warning("Corrupt aspect_lookup cache file: {} - Recreating...".format(self.cache_filepath))

    def write_cache(self):
        with open(self.cache_filepath, "w+") as af:
            json.dump(self.aspect_lookup, af)

    def _is_biological_process(self, go_term):
        bp_root = "GO:0008150"
        return go_term in self.aspect_lookup["P"] or go_term == bp_root

    def _is_molecular_function(self, go_term):
        mf_root = "GO:0003674"
        return go_term in self.aspect_lookup["F"] or go_term == mf_root

    def _is_cellular_component(self, go_term):
        cc_root = "GO:0005575"
        return go_term in self.aspect_lookup["C"] or go_term == cc_root

    def go_aspect(self, term):
        if self._is_molecular_function(term):
            return 'F'
        elif self._is_biological_process(term):
            return 'P'
        elif self._is_cellular_component(term):
            return 'C'
        else:
            aspect = super(CachedGoAspector, self).go_aspect(term)
            if aspect:
                self.aspect_lookup[aspect].append(term)
                return aspect
            return None



def format_extensions(ext_json):
    # print(ext_json)
    ej = json.loads(ext_json)
    ret = []
    # print(ej["union_of"][0]["intersection_of"])
    for i in ej["union_of"][0]["intersection_of"]:
        ret.append("{}({})".format(i["property"], i["filler"]))
    # print(ret)
    return ",".join(ret)

def get_relation_and_term(ext):
    ext_parts = ext.split("(")
    relation = ext_parts[0]  # i["property"]
    try:
        ext_term = ext_parts[1].split(")")[0]  # i["filler"]
    except:
        logger.warning(ext_parts)
        # [' dppa4']
        # $ grep dppa4 resources/mgi.gpa.test.gpa
        # MGI	MGI:2141165	acts_upstream_of_or_within	GO:0010628	MGI:MGI:5913752|PMID:20699224	ECO:0000315	MGI:MGI:6108355		20190124	MGI	has_regulation_target(Dppa2, dppa4, piwil2),occurs_in(EMAPA:16036)
        ext_term = ext_parts[1].split(")")[0]  # i["filler"]
    return relation, ext_term

def filter_evi_codes(annots):
    filtered = []
    for a in annots:
        if ecomap.ecoclass_to_coderef(a[5])[0] in acceptable_evidence_codes:
            filtered.append(a)
    return filtered

def filter_has_extension(annots):
    filtered = []
    for a in annots:
        if a[10] != "":
            filtered.append(a)
    return filtered

def filter_rule_validate_lines(annots, assoc_filter):
    filtered = []
    # Converts split GPAD line into ontobio assoc obj for passing into standard FilterRule validation
    gpad_parser = GpadParser()
    for a in annots:
        parse_result = gpad_parser.parse_line("\t".join(a))
        if len(parse_result.associations) > 0:
            # Right now, GpadParser only returns 0 or 1 associations
            assoc = parse_result.associations[0]
            assoc = extract_properties(assoc)
            if "annotation_properties" in assoc:
                a.append(assoc["annotation_properties"])
            if assoc_filter.validate_line(assoc):
                filtered.append(a)
    return filtered

def sum_combos(extension_counts, combo_list):
    cur_sum = 0
    for c in combo_list:
        if c in extension_counts:
            cur_sum += extension_counts[c]
    return cur_sum

def violates_combo_rule(extension_counts, list_of_combo_lists, max_allowed):
    for combo_list in list_of_combo_lists:
        if sum_combos(extension_counts, combo_list) > max_allowed:
            return True
    return False

def is_nested_occurs_in_grouping(extensions_list):
    # When annotation extensions are comma delimited and are from GO_CC, CL and an anatomy ontology
    # then the model should indicate GO_CC -> part_of->CL->part_of->anatomy.
    # Filter occurs_in extensions
    # Gather terms, arrange
    # When would multiple occurs_in's cause this to fail? Multiple occurs_in(GO:CC), unless CC's are related? Examples?
    #
    do_stuff = 1

class ExtensionValidityCheckResult:
    def __init__(self, is_valid, reason=None, offending_extension=None):
        self.is_valid = is_valid
        self.reason = reason
        self.offending_extension = offending_extension

    def __nonzero__(self):
        return self.is_valid


class ExtensionsMapper:
    def __init__(self, constraints_yaml, ontology=None):
        self.ontology = self.setup_ontologies(ontology)
        self.go_aspector = CachedGoAspector("resources/aspect_lookup.json", go_ontology=go_ontology)

        self.ext_relation_valid_patterns = []
        # Parsing formatted version of David's spreadsheet extensions_list_w_provided_bys_updated_20190328 into more rules
        with open(constraints_yaml) as rf:
            extension_constraints = yaml.load(rf)
            # rel_reader = csv.reader(rf, delimiter="\t")
            # next(rel_reader)  # Skip header row
            for ec in extension_constraints:
                relation = ec["relation"]
                namespaces = ec["namespaces"]
                root_terms = ec["primary_root_terms"]
                max_allowed = ec.get("cardinality")
                # if len(rl[3]) > 0:
                #     max_allowed = int(rl[3])
                ext_pattern = ExtRelationValidPattern(relation, namespaces, root_terms, max_allowed=max_allowed)
                self.ext_relation_valid_patterns.append(ext_pattern)

    @staticmethod
    def setup_ontologies(ontology=None):
        if ontology is None:
            return OntologyFactory().create("go")
        return ontology

    def is_valid_ext_pattern(self, primary_term, ext_relation, ext_namespace, occurence_count):
        for p in self.ext_relation_valid_patterns:
            if p.ext_relation == ext_relation and ext_namespace in p.ext_namespaces and \
                    not (p.max_allowed and occurence_count > p.max_allowed):
                # Check ancestors of query term - might take a while
                all_ancestors = GO_ONTOLOGY.ancestors(primary_term, reflexive=True)
                is_a_ancestors = GO_ONTOLOGY.subontology(all_ancestors).ancestors(primary_term,
                                                                                  relations=["subClassOf"],
                                                                                  reflexive=True)
                # Cache IS_A_ANCESTORS[primary_term] = is_a_ancestors ?
                # Valid pattern root term is an is_a ancestor of GPAD primary term
                for t in p.primary_term_roots:
                    if t in is_a_ancestors:
                        return True
        return False

    def following_rules(self, extension_list, aspect, term):
        ext_counts = {}
        for e in extension_list:
            if e in ext_counts:
                ext_counts[e] += 1
            else:
                ext_counts[e] = 1

        for ek in ext_counts.keys():
            if not self.is_valid_ext_pattern(term, *get_relation_and_term(ek), ext_counts[ek]):
                # return False
                # Pack this into Error class
                return ExtensionValidityCheckResult(is_valid=False, offending_extension=ek)

        combos_to_check_for = [
            ["occurs_in(UBERON)", "occurs_in(EMAPA)"]
        ]
        # Only allow 1 occurrence each of combos_to_check_for
        if violates_combo_rule(ext_counts, combos_to_check_for, 1):
            # return False
            return ExtensionValidityCheckResult(is_valid=False, reason="violates_combo_rule")

        # return True
        return ExtensionValidityCheckResult(is_valid=True)

    def filter_no_rules_broken(self, annots):
        filtered = []
        for a in annots:
            if not self.following_rules(a):
                filtered.append(a)
        return filtered

    def translate_relation_to_ro(self, relation_label):
        for n in self.ontology.nodes():
            node_label = self.ontology.label(n)
            if node_label == relation_label.replace("_", " "):
                return n

    def extensions_list(self, intersection_extensions, row_cols=[]):
        ext_list = []
        # Assuming these extensions are already separated by comma
        intersection_extensions = self.dedupe_extensions(intersection_extensions)
        for i in intersection_extensions:
            relation, ext_term = i['property'], i['filler']
            term_prefix = ext_term.split(":")[0]
            # is prefix for ontology or mod?
            if term_prefix in ontology_prefixes:
                if term_prefix == "GO":
                    # need to find aspect of GO term
                    go_aspect = self.go_aspector.go_aspect(ext_term)
                    if go_aspect is not None:
                        ont = "GO:" + go_aspect
                    else:
                        logger.warning("No aspect found for term: {}".format(ext_term))
                        ont = "GO"
                else:
                    ont = term_prefix
                term_prefix = ont
            else:
                term_prefix = "geneID"
            ext_list.append("{}({})".format(relation, term_prefix))
            # Track stats - make sure to get GO aspect from ont var
            if relation not in DISTINCT_EXTENSIONS:
                DISTINCT_EXTENSIONS[relation] = {}
            if term_prefix not in DISTINCT_EXTENSIONS[relation]:
                # should be checking for duplicate rows
                DISTINCT_EXTENSIONS[relation][term_prefix] = []
            # else:
            #     DISTINCT_EXTENSIONS[relation][term_prefix] += 1
            # if row_cols not in DISTINCT_EXTENSIONS[relation][term_prefix]:
            DISTINCT_EXTENSIONS[relation][term_prefix].append(row_cols)
        # ordering of extension relations may be inconsistent so sort
        return sorted(ext_list, key=str.lower)

    # Do we need this? Does this work? WE TOTALLY NEED THIS!!! At least maybe as an entry point to find what bucket an
    # annotation falls in.
    # HANDLE ASSOCIATION OBJECT_EXTENSIONS STRUCTURE
    def annot_following_rules(self, annot, aspect, term):
        ext_list = []
        #TODO for a in annot.split("|"):
        # extensions = annot.split(",")
        # annot["object_extensions"]
        # ext_list = self.extensions_list(extensions)
        ext_list = self.extensions_list(annot)
        # Standardize key - ex:
        #   ["part_of(GO:aspect),part_of(UBERON:)"]
        return self.following_rules(ext_list, aspect, term)


d = [
    "GeneDB_tsetse",
    "gonuts",
    "reactome",
    "isoform",
    "goa_pdb",
    "goa_uniprot_all.gaf",
]


if __name__ == "__main__":
    args = parser.parse_args()

    def get_filter_name(gpad_fname):
        if args.mod:
            filter_name = args.mod
        else:
            # Try matching filename to filter rule (e.g. wb.gpad to 'WB' to WBFilterRule)
            filter_name = os.path.basename(os.path.splitext(gpad_fname)[0]).upper()
        return filter_name

    bad_extensions = []

    # filenames = []
    # Use dict for holding different FilterRules for each file
    filenames = {}
    # data = []
    # fname = "/Users/ebertdu/go/go-pombase/gene_association.pombase-06-2018"
    # data = GafParser().parse(fname, skipheader=True)
    if args.filename is not None:
        # filenames.append(args.filename)
        filter_name = get_filter_name(args.filename)
        filter_rule = get_filter_rule(filter_name)
        filenames[args.filename] = filter_rule
        # data = GafParser().parse(args.filename, skipheader=True)
    elif args.dir is not None:
        for fname in os.listdir(args.dir):
            # print("Loading file:", fname)
            nono_in_fname = False
            for nono in d:
                if nono in fname:
                    nono_in_fname = True
            if fname.endswith(".tsv") or nono_in_fname:
                continue
            # filenames.append(args.dir + fname)
            filter_name = get_filter_name(fname)
            filenames[args.dir + fname] = get_filter_rule(filter_name)
            # data = data + GafParser().parse(fname, skipheader=True)

    # all_dict = {}
    extensions_mapper = ExtensionsMapper(constraints_yaml=args.constraints_yaml)
    gpad_parser = GpadParser()
    print("Creating extension dictionary...")
    ext_dict = {}
    ext_dict['F'] = {}
    ext_dict['P'] = {}
    ext_dict['C'] = {}
    for fname in filenames:
        with open(fname) as f:
            data = []
            print("Loading file:", fname)
            for l in f.readlines():
                if not l.startswith("!"):
                    parts = l.split("\t")
                    # if parts[15] != "" and parts[6] in acceptable_evidence_codes:
                    data.append(parts)
            print("# of GPAD lines in file:", len(data))
            data = filter_has_extension(data)
            print("# of GPAD lines having extensions:", len(data))
            # filter_rule = get_filter_rule(args.mod)
            filter_rule = filenames[fname]
            assoc_filter = AssocFilter(filter_rule)
            data = filter_rule_validate_lines(data, assoc_filter)
            print("Total GPAD count after applying {}: {}".format(filter_rule.__class__.__name__, len(data)))

            for g in data:
                go_term = g[3]
                aspect = extensions_mapper.go_aspector.go_aspect(go_term)
                split_line = SplitLine(line="\t".join(g), values=g, taxon="")  # Needed for ontobio error handling
                ontobio_extensions = gpad_parser._parse_full_extension_expression(g[10], split_line)
                ontobio_extensions = extensions_mapper.dedupe_extensions(ontobio_extensions)
                # ontobio_pattern = {
                #     'union_of': [
                #         {
                #             'intersection_of': [
                #                 {'property': 'part_of', 'filler': 'CL:0000678'},
                #                 {'property': 'part_of', 'filler': 'EMAPA:16525'}
                #             ]
                #         },
                #         {
                #               'intersection_of': [
                #                   {'property': 'part_of', 'filler': 'CL:0000678'},
                #                   {'property': 'part_of', 'filler': 'EMAPA:16525'}
                #               ]
                #         }
                #     ]
                # }
                for onto_ext in ontobio_extensions:
                    ext_list = extensions_mapper.extensions_list(onto_ext['intersection_of'], g)
                    check_ext_result = extensions_mapper.following_rules(ext_list, aspect, go_term)
                    if not check_ext_result.is_valid:
                        ext_key = ",".join(ext_list)
                        offending_extension = check_ext_result.offending_extension
                        if offending_extension is None:
                            offending_extension = check_ext_result.reason
                        bad_extensions.append([":".join(g[0:2]), go_term, GO_ONTOLOGY.label(go_term), offending_extension, g[10]])
                        if ext_key not in ext_dict[aspect]:
                            ext_dict[aspect][ext_key] = [g]
                        elif g not in ext_dict[aspect][ext_key]:
                            ext_dict[aspect][ext_key].append(g)

            for aspect in ['F','P','C']:
                max_count = 0
                top_k = None
                example_v = None
                for k, v in ext_dict[aspect].items():
                    if len(v) > max_count:
                        max_count = len(v)
                        # print(max_count)
                        top_k = k
                        example_v = v[0]

    def assigner_count(annots, assign):
        count = 0
        for a in annots:
            if a[9] == assign:
                count += 1
        return count

    cols = ['Aspect', 'Total count', 'Extension']
    all_assigners = []
    for aspect in ['F', 'P', 'C']:
        for k, v in ext_dict[aspect].items():
            for a in v:
                if a[9] not in all_assigners:
                    all_assigners.append(a[9])
                    cols.append(a[9])

    def parse_pattern_sourcefile(sourcefile):
        parsed_patterns = []
        with open(sourcefile) as sf:
            for pl in sf.readlines():
                pl = pl.rstrip()
                parsed_patterns.append(pl)
        return parsed_patterns

    class GpadWriter:
        def __init__(self, gpad_file):
            self.gpad_file = gpad_file
            self.writer = csv.writer(pattern_gpad, delimiter="\t")

        def writerow(self, row):
            self.writer.writerow(row)

    class WriterCollection:
        def __init__(self):
            self.writers = {}
            self.rows = {}

        def set_writer(self, writer, writer_name):
            self.writers[writer_name] = writer
            self.rows[writer_name] = []


    patterns = []
    writers = WriterCollection()
    if args.pattern or args.pattern_sourcefile:
        if args.pattern_sourcefile:
            patterns = parse_pattern_sourcefile(args.pattern_sourcefile)
            # writers = {}
            for patt in patterns:
                pattern_outfile = "{}.gpad".format(patt)
                pattern_gpad = open(pattern_outfile, "w+")
                pattern_gpad_writer = GpadWriter(pattern_gpad)
                writers.set_writer(pattern_gpad_writer, patt)
        else:
            patterns.append(args.pattern)
            pattern_outfile = "{}.gpad".format(args.pattern)
            if args.pattern_outfile:
                pattern_outfile = args.pattern_outfile
            pattern_gpad = open(pattern_outfile, "w+")
            pattern_gpad_writer = GpadWriter(pattern_gpad)
            writers.set_writer(pattern_gpad_writer, args.pattern)
    out_file = "all.tsv"
    if args.out_file:
        out_file = args.out_file
    with open(out_file, 'w') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(cols)
        for aspect in ['F', 'P', 'C']:
            max_count = 0
            top_k = None
            example_v = None
            for k, v in ext_dict[aspect].items():
                row_to_write = [aspect, len(v), k]
                if len(patterns) > 0:
                    for patt in patterns:
                        # if k == patt:
                        if patt in k:
                            for a in v:
                                writers.rows[patt].append(a[0:len(a)-1])
                                # writers.writers[patt].writerow(a[0:len(a)-1])
                for assigner in all_assigners:
                    a_count = assigner_count(v, assigner)
                    row_to_write.append(a_count)
                writer.writerow(row_to_write)
    for writer_name in writers.writers:
        for row in writers.rows[writer_name]:
            writers.writers[writer_name].writerow(row)
        gpad_file = writers.writers[writer_name].gpad_file
        print("Offending GPAD lines written to:", gpad_file.name)
        gpad_file.close()

    wanted_gafs = []
    leftovers_out_file = "leftovers.gpad"
    if args.leftovers_out_file:
        leftovers_out_file = args.leftovers_out_file
    with open(leftovers_out_file, 'w') as wf:
        for k in ext_dict['P'].keys():
            if 'has_regulation_target' in k:
                wanted_gafs = wanted_gafs + ext_dict['P'][k]
                for g in ext_dict['P'][k]:
                    wf.write("\t".join(g))

    if args.extensions_list:
        with open("distinct_extensions.txt", "w+") as de_f:
            de_writer = csv.writer(de_f, delimiter="\t")
            de_writer.writerow(["pattern", "namespaces", "usage count", "line count", "RO code"])
            for rel in DISTINCT_EXTENSIONS:
                distinct_lines = []
                usage_count = 0
                ro_rel = extensions_mapper.translate_relation_to_ro(rel)
                for prefix in DISTINCT_EXTENSIONS[rel]:
                    usage_count += len(DISTINCT_EXTENSIONS[rel][prefix])
                    # distinct_lines = []
                    for line in DISTINCT_EXTENSIONS[rel][prefix]:
                        if line not in distinct_lines:
                            distinct_lines.append(line)
                    # line_count = len(distinct_lines)
                    # de_writer.writerow(["{}({})".format(rel, prefix), len(DISTINCT_EXTENSIONS[rel][prefix]), line_count])
                line_count = len(distinct_lines)
                de_writer.writerow([rel, ",".join(DISTINCT_EXTENSIONS[rel].keys()), usage_count, line_count, ro_rel])

    bad_extensions_fname = date_fname("bad_extensions.tsv")
    with open(bad_extensions_fname, "w+") as bef:
        be_writer = csv.writer(bef, delimiter="\t")
        be_writer.writerow(["DB Object", "Primary term", "Label", "Offending extension", "Full extensions"])
        for be in bad_extensions:
            be_writer.writerow(be)