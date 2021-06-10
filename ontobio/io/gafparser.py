import re
import logging
import json

from typing import List, Tuple, Set, Dict
from dataclasses import dataclass

from prefixcommons import curie_util

from ontobio.io import assocparser
from ontobio.io import parser_version_regex
from ontobio.io.assocparser import ENTITY, EXTENSION, ANNOTATION, Report
from ontobio.io import qc
from ontobio.io import entityparser
from ontobio.io import entitywriter
from ontobio.model import association
from ontobio.model import collections
from ontobio.ecomap import EcoMap
from ontobio.rdfgen import relations
from ontobio.ontol import Ontology

import dateutil.parser
import functools

import click

logger = logging.getLogger(__name__)




gaf_line_validators = {
    "default": assocparser.ColumnValidator(),
    "qualifier2_1": assocparser.Qualifier2_1(),
    "qualifier2_2": assocparser.Qualifier2_2(),
    "curie": assocparser.CurieValidator(),
    "taxon": assocparser.TaxonValidator()
}


def protein_complex_sublcass_closure(ontology: Ontology) -> Set[str]:
    protein_containing_complex = association.Curie(namespace="GO", identity="0032991")
    children_of_complexes = set(ontology.descendants(str(protein_containing_complex), relations=["subClassOf"], reflexive=True))
    return children_of_complexes


class GafParser(assocparser.AssocParser):
    """
    Parser for GO GAF format
    """

    ANNOTATION_CLASS_COLUMN=4

    def __init__(self, config=None, group="unknown", dataset="unknown", bio_entities=None):
        """
        Arguments:
        ---------

        config : a AssocParserConfig object
        """
        self.config = config
        self.group = group
        self.version = None
        self.default_version = "2.1"
        self.bio_entities = bio_entities
        if self.bio_entities is None:
            self.bio_entities = collections.BioEntities(dict())

        self.cell_component_descendants_closure = None

        if config is None:
            self.config = assocparser.AssocParserConfig()
        self.report = assocparser.Report(group=group, dataset=dataset, config=self.config)
        # self.gpi = None
        if self.config.gpi_authority_path is not None:
            gpi_paths = self.config.gpi_authority_path
            if isinstance(gpi_paths, str):
                gpi_paths = [gpi_paths]
            for gpi_path in gpi_paths:
                gpi_bio_entities = collections.BioEntities.load_from_file(gpi_path)
                self.bio_entities.merge(gpi_bio_entities)
                print("Loaded {} entities from {}".format(len(gpi_bio_entities.entities.keys()), gpi_path))

    def gaf_version(self) -> str:
        if self.version:
            return self.version
        else:
            return self.default_version

    def qualifier_parser(self) -> assocparser.ColumnValidator:
        if self.gaf_version() == "2.2":
            return assocparser.Qualifier2_2()

        return assocparser.Qualifier2_1()

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

    def make_internal_cell_component_closure(self):
        if self.config.ontology:
            self.cell_component_descendants_closure = protein_complex_sublcass_closure(self.config.ontology)

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
            # Save off version info here
            if self.version is None:
                # We are still looking
                parsed = parser_version_regex.findall(line)
                if len(parsed) == 1:
                    filetype, version, _ = parsed[0]
                    if version == "2.2":
                        logger.info("Detected GAF version 2.2")
                        self.version = version
                    else:
                        logger.info("Detected GAF version {}, so using 2.1".format(version))
                        self.version = self.default_version
                        # Compute the cell component subclass closure
                        self.make_internal_cell_component_closure()

            return assocparser.ParseResult(line, [{ "header": True, "line": line.strip() }], False)

        # At this point, we should have gone through all the header, and a version number should be established
        if self.version is None:
            logger.warning("No version number found for this file so we will assume GAF version: {}".format(self.default_version))
            self.version = self.default_version
            self.make_internal_cell_component_closure()

        vals = [el.strip() for el in line.split("\t")]

        # GAF v1 is defined as 15 cols, GAF v2 as 17.
        # We treat everything as GAF2 by adding two blank columns.
        # TODO: check header metadata to see if columns corresponds to declared dataformat version

        parsed = to_association(list(vals), report=self.report, qualifier_parser=self.qualifier_parser(), bio_entities=self.bio_entities)
        if parsed.associations == []:
            return parsed

        assoc = parsed.associations[0]

        # Qualifier is index 3
        # If we are 2.1, and qualifier has no relation
        # Also must have an ontology
        # Then upgrade
        # For https://github.com/geneontology/go-site/issues/1558
        if self.gaf_version() == "2.1" and (vals[3] == "" or vals[3] == "NOT") and self.config.ontology:
            assoc = self.upgrade_empty_qualifier(assoc)

        ## Run GO Rules, save split values into individual variables
        # print("Config is {}".format(self.config.__dict__.keys()))
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

        assoc = go_rule_results.annotation  # type: association.GoAssociation
        split_line = assocparser.SplitLine(line=line, values=vals, taxon=str(assoc.object.taxon))

        if self.config.group_idspace is not None and assoc.provided_by not in self.config.group_idspace:
            self.report.warning(line, Report.INVALID_ID, assoc.provided_by,
                "GORULE:0000027: assigned_by is not present in groups reference", taxon=str(assoc.object.taxon), rule=27)

        db = assoc.subject.id.namespace
        if self.config.entity_idspaces is not None and db not in self.config.entity_idspaces:
            # Are we a synonym?
            upgrade = self.config.entity_idspaces.reverse(db)
            if upgrade is not None:
                # If we found a synonym
                self.report.warning(line, Report.INVALID_ID_DBXREF, db, "GORULE:0000027: {} is a synonym for the correct ID {}, and has been updated".format(db, upgrade), taxon=str(assoc.object.taxon), rule=27)
                assoc.subject.id.namespace = upgrade

        ## --
        ## db + db_object_id. CARD=1
        ## --assigned_by
        if not self._validate_id(str(assoc.subject.id), split_line, allowed_ids=self.config.entity_idspaces):
            return assocparser.ParseResult(line, [], True)

        # Using a given gpi file to validate the gene object
        # if self.gpi is not None:
        #     entity = self.gpi.get(str(assoc.subject.id), None)
        #     if entity is not None:
        #         assoc.subject.label = entity["symbol"]
        #         assoc.subject.fullname = entity["name"]
        #         assoc.subject.synonyms = entity["synonyms"].split("|")
        #         assoc.subject.type = entity["type"]

        if not self._validate_id(str(assoc.object.id), split_line, context=ANNOTATION):
            print("skipping because {} not validated!".format(assoc.object.id))
            return assocparser.ParseResult(line, [], True)

        valid_goid = self._validate_ontology_class_id(str(assoc.object.id), split_line)
        if valid_goid is None:
            return assocparser.ParseResult(line, [], True)
        assoc.object.id = association.Curie.from_str(valid_goid)

        references = self.validate_curie_ids(assoc.evidence.has_supporting_reference, split_line)
        if references is None:
            # Reporting occurs in above function call
            return assocparser.ParseResult(line, [], True)

        # With/From
        for wf in assoc.evidence.with_support_from:
            validated = self.validate_curie_ids(wf.elements, split_line)
            if validated is None:
                return assocparser.ParseResult(line, [], True)

        # validation
        self._validate_symbol(assoc.subject.label, split_line)


        ## --
        ## taxon CARD={1,2}
        ## --
        ## if a second value is specified, this is the interacting taxon
        ## We do not use the second value
        valid_taxon = self._validate_taxon(str(assoc.object.taxon), split_line)
        valid_interacting = self._validate_taxon(str(assoc.interacting_taxon), split_line) if assoc.interacting_taxon else True
        if not valid_taxon:
            self.report.error(line, assocparser.Report.INVALID_TAXON, str(assoc.object.taxon), "Taxon ID is invalid", rule=27)
        if not valid_interacting:
            self.report.error(line, assocparser.Report.INVALID_TAXON, str(assoc.interacting_taxon), "Taxon ID is invalid", rule=27)
        if (not valid_taxon) or (not valid_interacting):
            return assocparser.ParseResult(line, [], True)

        return assocparser.ParseResult(line, [assoc], False, vals[6])

    def upgrade_empty_qualifier(self, assoc: association.GoAssociation) -> association.GoAssociation:
        """
        From https://github.com/geneontology/go-site/issues/1558

        For GAF 2.1 we will apply an algorithm to find a best fit relation if the qualifier column is empty.
        If the qualifiers field is empty, then:
            If the GO Term is exactly GO:008150 Biological Process, then the qualifier should be `involved_in`
            If the GO Term is exactly GO:0008372 Cellular Component, then the qualifer should be `is_active_in`
            If the GO Term is a Molecular Function, then the new qualifier should be `enables`
            If the GO Term is a Biological Process, then the new qualifier should be `acts_upstream_or_within
            Otherwise for Cellular Component, if it's subclass of anatomical structure, than use `located_in`
                and if it's a protein-containing complexes, use `part_of`
        :param assoc: GoAssociation
        :return: the possibly upgraded GoAssociation
        """
        term = str(assoc.object.id)
        namespace = self.config.ontology.obo_namespace(term)

        if term == "GO:0008150":
            involved_in = association.Curie(namespace="RO", identity="0002331")
            assoc.qualifiers = [involved_in]
            assoc.relation = involved_in
        elif term == "GO:0008372":
            is_active_in = association.Curie(namespace="RO", identity="0002432")
            assoc.qualifiers = [is_active_in]
            assoc.relation = is_active_in
        elif namespace == "molecular_function":
            enables = association.Curie(namespace="RO", identity="0002327")
            assoc.qualifiers = [enables]
            assoc.relation = enables
        elif namespace == "biological_process":
            acts_upstream_or_within = association.Curie(namespace="RO", identity="0002264")
            assoc.qualifiers = [acts_upstream_or_within]
            assoc.relation = acts_upstream_or_within
        elif namespace == "cellular_component":
            if term in self.cell_component_descendants_closure:
                part_of = association.Curie(namespace="BFO", identity="0000050")
                assoc.qualifiers = [part_of]
                assoc.relation = part_of
            else:
                located_in = association.Curie(namespace="RO", identity="0001025")
                assoc.qualifiers = [located_in]
                assoc.relation = located_in

        self.report.warning(assoc.source_line, Report.INVALID_QUALIFIER,
                            "EMPTY", "GORULE:0000059 Upgrading qualifier/relation to {} when reading GAF 2.1".format(assoc.relation),
                            taxon=str(assoc.subject.taxon), rule=59)
        return assoc

ecomap = EcoMap()
ecomap.mappings()

def to_association(gaf_line: List[str], report=None, group="unknown", dataset="unknown", qualifier_parser=assocparser.Qualifier2_1(), bio_entities=None) -> assocparser.ParseResult:
    report = Report(group=group, dataset=dataset) if report is None else report
    bio_entities = collections.BioEntities(dict()) if bio_entities is None else bio_entities
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
            msg="There were {columns} columns found in this line, and there should be 15 (for GAF v1) or 17 (for GAF v2)".format(columns=len(gaf_line)), rule=1)
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
    if gaf_line[REFERENCE_INDEX] == "":
        report.error(source_line, Report.INVALID_ID, "EMPTY", "reference column 6 is empty", taxon=gaf_line[TAXON_INDEX], rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    parsed_taxons_result = gaf_line_validators["taxon"].validate(gaf_line[TAXON_INDEX])  # type: assocparser.ValidateResult
    if not parsed_taxons_result.valid:
        report.error(source_line, Report.INVALID_TAXON, parsed_taxons_result.original, parsed_taxons_result.message, taxon=parsed_taxons_result.original, rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    taxon = parsed_taxons_result.parsed[0]

    date = assocparser.parse_date(gaf_line[13], report, source_line)
    if date is None:
        return assocparser.ParseResult(source_line, [], True, report=report)

    interacting_taxon = parsed_taxons_result.parsed[1] if len(parsed_taxons_result.parsed) == 2 else None
    subject_curie = association.Curie(gaf_line[0], gaf_line[1])
    subject = association.Subject(subject_curie, gaf_line[2], [gaf_line[9]], gaf_line[10].split("|"), [association.map_gp_type_label_to_curie(gaf_line[11])], taxon)
    gpi_entity = bio_entities.get(subject_curie)
    if gpi_entity is not None and subject != gpi_entity:
        subject = gpi_entity

    aspect = gaf_line[8]
    negated, relation_label, qualifiers = assocparser._parse_qualifier(gaf_line[3], aspect)
    # Note: Relation label is grabbed from qualifiers, if any exist in _parse_qualifier
    qualifiers = [association.Curie.from_str(curie_util.contract_uri(relations.lookup_label(q), strict=False)[0]) for q in qualifiers]

    # column 4 is qualifiers -> index 3
    # For allowed, see http://geneontology.org/docs/go-annotations/#annotation-qualifiers
    # We use the below validate to check validaty if qualifiers, not as much to *parse* them into the GoAssociation object.
    # For GoAssociation we will use the above qualifiers list. This is fine because the above does not include `NOT`, etc
    # This is confusing, and we can fix later on by consolidating qualifier and relation in GoAssociation.
    parsed_qualifiers = qualifier_parser.validate(gaf_line[3])
    if not parsed_qualifiers.valid:
        report.error(source_line, Report.INVALID_QUALIFIER, parsed_qualifiers.original, parsed_qualifiers.message, taxon=gaf_line[TAXON_INDEX], rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    object = association.Term(association.Curie.from_str(gaf_line[4]), taxon)
    if isinstance(object, association.Error):
        report.error(source_line, Report.INVALID_SYMBOL, gaf_line[4], "Problem parsing GO Term", taxon=gaf_line[TAXON_INDEX], rule=1)

    # References
    references = [association.Curie.from_str(e) for e in gaf_line[5].split("|") if e]
    for r in references:
        if isinstance(r, association.Error):
            report.error(source_line, Report.INVALID_SYMBOL, gaf_line[5], "Problem parsing references", taxon=gaf_line[TAXON_INDEX], rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    gorefs = [ref for ref in references if ref.namespace == "GO_REF"] + [None]
    eco_curie = ecomap.coderef_to_ecoclass(gaf_line[6], reference=gorefs[0])
    if eco_curie is None:
        report.error(source_line, Report.UNKNOWN_EVIDENCE_CLASS, gaf_line[6], msg="Expecting a known ECO GAF code, e.g ISS", rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    withfroms = association.ConjunctiveSet.str_to_conjunctions(gaf_line[7])
    if isinstance(withfroms, association.Error):
        report.error(source_line, Report.INVALID_SYMBOL, gaf_line[7], "Problem parsing with/from", taxon=gaf_line[TAXON_INDEX], rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    evidence_type = association.Curie.from_str(eco_curie)
    if isinstance(evidence_type, association.Error):
        report.error(source_line, Report.INVALID_SYMBOL, gaf_line[6], "Problem parsing evidence type", taxon=gaf_line[TAXON_INDEX], rule=1)

    evidence = association.Evidence(association.Curie.from_str(eco_curie), references, withfroms)
    if any([isinstance(e, association.Error) for e in evidence.has_supporting_reference]):
        first_error = [e for e in evidence.has_supporting_reference if isinstance(e, association.Error)][0]
        report.error(source_line, Report.INVALID_SYMBOL, gaf_line[5], first_error.info, taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    subject_extensions = []
    if gaf_line[16]:
        subject_filler = association.Curie.from_str(gaf_line[16])
        if isinstance(subject_filler, association.Error):
            report.error(source_line, assocparser.Report.INVALID_ID, gaf_line[16], subject_filler.info, taxon=str(taxon), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)
        # filler is not an Error, so keep moving
        subject_extensions.append(association.ExtensionUnit(association.Curie.from_str("rdfs:subClassOf"), subject_filler))

    conjunctions = []
    if gaf_line[15]:
        conjunctions = association.ConjunctiveSet.str_to_conjunctions(
            gaf_line[15],
            conjunct_element_builder=lambda el: association.ExtensionUnit.from_str(el))

        if isinstance(conjunctions, association.Error):
            report.error(source_line, Report.EXTENSION_SYNTAX_ERROR, conjunctions.info, "extensions should be relation(curie) and relation should have corresponding URI", taxon=str(taxon), rule=1)
            return assocparser.ParseResult(source_line, [], True, report=report)

    relation_uri = relations.lookup_label(relation_label)
    if relation_uri is None:
        report.error(source_line, assocparser.Report.INVALID_QUALIFIER, relation_label, "Could not find CURIE for relation `{}`".format(relation_label), taxon=str(taxon), rule=1)
        return assocparser.ParseResult(source_line, [], True, report=report)

    # We don't have to check that this is well formed because we're grabbing it from the known relations URI map.
    relation_curie = association.Curie.from_str(curie_util.contract_uri(relation_uri)[0])

    a = association.GoAssociation(
        source_line="\t".join(gaf_line),
        subject=subject,
        relation=relation_curie,
        object=object,
        negated=negated,
        qualifiers=qualifiers,
        aspect=aspect,
        interacting_taxon=interacting_taxon,
        evidence=evidence,
        subject_extensions=subject_extensions,
        object_extensions=conjunctions,
        provided_by=gaf_line[14],
        date=date,
        properties={})

    return assocparser.ParseResult(source_line, [a], False, report=report)
