import json
import enum
import collections
import datetime
import copy
import logging

from dataclasses import dataclass

from typing import List, Dict, Any, Optional, Set, Tuple, Union
from prefixcommons import curie_util
from requests.models import REDIRECT_STATI
from ontobio import ontol
from ontobio import ecomap
from ontobio.io import assocparser, gafparser
from ontobio.io import gaference
from ontobio.model import association
from ontobio.rdfgen import relations

logger = logging.getLogger(__name__)

FailMode = enum.Enum("FailMode", {"SOFT": "soft", "HARD": "hard"})
ResultType = enum.Enum("Result", {"PASS": "Pass", "WARNING": "Warning", "ERROR": "Error"})
RepairState = enum.Enum("RepairState", {"OKAY": "Okay", "REPAIRED": "Repaired", "FAILED": "Failed"})


# TestResult = collections.namedtuple("TestResult", ["result_type", "message", "result"])
class TestResult(object):
    """
    Represents the result of a single association.GoAssociation being validated on some rule
    """
    def __init__(self, result_type: ResultType, message: str, result):
        """
        Create a new TestResult

        Args:
            result_type (ResultType): enum of PASS, WARNING, ERROR. Both WARNINGs and ERRORs are reported, but ERROR will filter the offending GoAssociation
            message (str): Description of the failure of GoAssociation to pass a rule. This is usually just the rule title
            result: [description] True if the GoAssociation passes, False if not. If it's repaired, this is the updated, repaired, GoAssociation
        """
        self.result_type = result_type
        self.message = message
        self.result = result


"""
Send True for passes, and this returns the PASS ResultType, and if False, then
depending on the fail mode it returns either WARNING or ERROR ResultType.
"""


def result(passes: bool, fail_mode: FailMode) -> ResultType:
    """
    Send True for passes, and this returns the PASS ResultType, and if False, then
    depending on the fail mode it returns either WARNING or ERROR ResultType.
    """
    if passes:
        return ResultType.PASS

    # Else we didn't pass
    if fail_mode == FailMode.SOFT:
        return ResultType.WARNING

    if fail_mode == FailMode.HARD:
        return ResultType.ERROR


def repair_result(repair_state: RepairState, fail_mode: FailMode) -> ResultType:
    """
    Returns ResultType.PASS if the repair_state is OKAY, and WARNING if REPAIRED.

    This is used by RepairRule implementations.

    Args:
        repair_state (RepairState): If the GoAssocition was repaired during a rule, then this should be RepairState.REPAIRED, otherwise RepairState.OKAY
        fail_mode (FailMode): [description]

    Returns:
        ResultType: [description]
    """
    if repair_state == RepairState.OKAY:
        return ResultType.PASS

    if repair_state == RepairState.REPAIRED:
        return ResultType.WARNING

    return result(False, fail_mode)


class GoRule(object):

    def __init__(self, id, title, fail_mode: FailMode, tags=[]):
        self.id = id
        self.title = title
        self.fail_mode = fail_mode
        self.run_context_tags = set(tags)

    def _list_terms(self, pipe_separated):
        terms = pipe_separated.split("|")
        terms = [t for t in terms if t != ""] # Remove empty strings
        return terms

    def _result(self, passes: bool) -> TestResult:
        return TestResult(result(passes, self.fail_mode), self.title, passes)

    def _is_run_from_context(self, config: assocparser.AssocParserConfig) -> bool:
        rule_tags_to_match = set([ "context-{}".format(c) for c in config.rule_contexts ])
        # If there is no context, then run
        # Or, if any run_context_tags is in rule_tags_to_match, then run
        return len(self.run_context_tags) == 0 or any(self.run_context_tags & rule_tags_to_match)

    def _run_if_context(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        if not config.rule_set.should_run_rule(self.id.split(":")[1]):
            # We check that this rule can be run based on the ID and what is in the config rule_set.
            # If we should not run the rule, we'll auto-pass it here.
            # In the future, we could use a new result type, SKIP here.
            return TestResult(ResultType.PASS, "", annotation)

        result = TestResult(ResultType.PASS, "", annotation)
        if self._is_run_from_context(config):
            result = self.test(annotation, config, group=group)

        return result

    def run_test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        result = self._run_if_context(annotation, config, group=group)
        result.result = annotation
        return result

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        """
        Subclasses should override this function to implement the logic of the rule.

        Args:
            annotation (association.GoAssociation): The incoming annotation under test
            config (assocparser.AssocParserConfig): The configuration object defined for this execution of the rules. This should stay more or less constant across each rule test run as well as across each annotation being passed into the rules engine. This holds things like the ontology, etc.
            group ([type], optional): The name of the upstream resource group whose annotation is being tested. This may be None.

        Returns:
            TestResult: See documentation for TestResult above
        """
        pass


class RepairRule(GoRule):

    def __init__(self, id, title, fail_mode, tags=[]):
        super().__init__(id, title, fail_mode, tags)

    def message(self, state: RepairState) -> str:
        message = ""
        if state == RepairState.REPAIRED:
            message = "Found violation of: `{}` but was repaired".format(self.title)
        elif state == RepairState.FAILED:
            message = "Found violatoin of: `{}` and could not be repaired".format(self.title)

        return message

    def run_test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        result = self._run_if_context(annotation, config, group=group)
        return result

    def repair(self, annotation: association.GoAssociation, group=None) -> Tuple[List, RepairState]:
        pass


class GoRule02(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000002", "No 'NOT' annotations to 'protein binding ; GO:0005515'", FailMode.SOFT)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:

        fails = (str(annotation.object.id) == "GO:0005515" and annotation.negated)
        return self._result(not fails)


class GoRule06(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000006", "IEP and HEP usage is restricted to terms from the Biological Process ontology", FailMode.HARD)
        self.iep = "ECO:0000270"
        self.hep = "ECO:0007007"

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        if config.ontology is None:
            return self._result(True)

        go_namespace = [predval for predval in config.ontology.get_graph().nodes.get(str(annotation.object.id), {}).get("meta", {}).get("basicPropertyValues", []) if predval["pred"]=="OIO:hasOBONamespace"]
        evidence = str(annotation.evidence.type)
        fails = evidence in [self.iep, self.hep] and "biological_process" not in [o["val"] for o in go_namespace]
        return self._result(not fails)


class GoRule07(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000007", "IPI should not be used with catalytic activity molecular function terms", FailMode.SOFT)
        self.children_of_catalytic_activity = None

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        catalytic_activity = "GO:0003824"
        if config.ontology is not None and self.children_of_catalytic_activity is None:
            # We'll define children_of_catalytic_activity if we have an ontology *and* if we haven't defined it before already
            self.children_of_catalytic_activity = set(config.ontology.descendants(catalytic_activity, relations=["subClassOf"], reflexive=True))

        goterm = str(annotation.object.id)
        evidence = str(annotation.evidence.type)

        fails = False
        if self.children_of_catalytic_activity is not None:
            # We fail if evidence is IPI and the goterm is a subclass of catalytic activity, else we good
            fails = evidence == "ECO:0000353" and goterm in self.children_of_catalytic_activity

        return self._result(not fails)


class GoRule08(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000008", "No annotations should be made to uninformatively high level terms", FailMode.SOFT)
        self.do_not_annotate = None
        self.do_not_manually_annotate = None

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        # Cache the subsets
        if config.ontology is None:
            return self._result(True)

        if self.do_not_annotate is None and config.ontology is not None:
            self.do_not_annotate = set(config.ontology.extract_subset("gocheck_do_not_annotate"))
            self.do_not_manually_annotate = set(config.ontology.extract_subset("gocheck_do_not_manually_annotate"))
        elif self.do_not_annotate is None and config.ontology is None:
            self.do_not_annotate = []
            self.do_not_manually_annotate = []

        goid = str(annotation.object.id)
        evidence = str(annotation.evidence.type)

        auto_annotated = goid in self.do_not_annotate
        manually_annotated = evidence != "ECO:0000501" and goid in self.do_not_manually_annotate
        not_high_level = not (auto_annotated or manually_annotated)

        t = result(not_high_level, self.fail_mode)
        return TestResult(t, self.title, not_high_level)


class GoRule11(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000011", "ND annotations to root nodes only", FailMode.HARD)
        self.root_go_classes = ["GO:0003674", "GO:0005575", "GO:0008150"]
        self.nd = "ECO:0000307"

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        goclass = str(annotation.object.id)
        evidence = str(annotation.evidence.type)

        # If we see a bad evidence, and we're not in a paint file then fail.
        # We're good if both predicates are true, or neither are true
        success = (evidence == self.nd and goclass in self.root_go_classes) or (evidence != self.nd and goclass not in self.root_go_classes)
        return self._result(success)


class GoRule13(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000013", "Taxon-appropriate annotation check", FailMode.HARD)
        self.non_experimental_evidence = set(["ECO:0000318", "ECO:0000320", "ECO:0000321", "ECO:0000305", "ECO:0000247", "ECO:0000255", "ECO:0000266", "ECO:0000250", "ECO:0000303", "ECO:0000245", "ECO:0000304", "ECO:0000307", "ECO:0000501"])

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        if config.annotation_inferences is None:
            # Auto pass if we don't have inferences
            return self._result(True)

        if annotation.negated:
            # The rule is passed if the annotation is negated
            return self._result(True)

        inference_results = gaference.produce_inferences(annotation, config.annotation_inferences)  # type: List[gaference.InferenceResult]
        taxon_passing = True
        for result in inference_results:
            if result.problem == gaference.ProblemType.TAXON:
                taxon_passing = False
                break

        if taxon_passing:
            return self._result(True)
        else:
            # Filter non experimental evidence
            if str(annotation.evidence.type) in self.non_experimental_evidence:
                return self._result(False)
            else:
                # Only submit a warning/report if we are an experimental evidence
                return TestResult(ResultType.WARNING, self.title, False)


class GoRule15(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000015", "Dual species taxon check", FailMode.SOFT)
        self.allowed_dual_species_terms = None

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:

        # Cache the allowed terms
        if self.allowed_dual_species_terms is None and config.ontology is not None:
            interaction_terms = config.ontology.descendants("GO:0044419", relations=["subClassOf", "BFO:0000050"], reflexive=True)
            interspecies_interactions_regulation = config.ontology.descendants("GO:0043903", relations=["subClassOf"], reflexive=True)
            host_cellular_component = config.ontology.descendants("GO:0018995", relations=["subClassOf"], reflexive=True)
            self.allowed_dual_species_terms = set(interaction_terms + interspecies_interactions_regulation + host_cellular_component)
        elif config.ontology is None:
            return self._result(True)

        passes = False
        if self.allowed_dual_species_terms is not None:
            dual = annotation.interacting_taxon is not None
            goterm = str(annotation.object.id)

            # We fail if we are a dual taxon and then the term is not in this list
            # This is the same as dual -> goterm in list
            # Implication rewritten is Not P OR Q
            passes = not dual or (goterm in self.allowed_dual_species_terms)

        return self._result(passes)


class GoRule16(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000016", "All IC annotations should include a GO ID in the \"With/From\" column", FailMode.HARD)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        evidence = str(annotation.evidence.type)
        withfrom = annotation.evidence.with_support_from

        okay = True
        if evidence == "ECO:0000305":
            only_go = [t for conjunctions in withfrom for t in conjunctions.elements if t.namespace == "GO"] # Filter terms that aren't GO terms
            okay = len(only_go) >= 1

        return self._result(okay)


class GoRule17(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000017", "IDA annotations must not have a With/From entry", FailMode.SOFT)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        evidence = str(annotation.evidence.type)
        withfrom = annotation.evidence.with_support_from

        if evidence == "ECO:0000314":
            return self._result(not bool(withfrom))
        else:
            return self._result(True)


class GoRule18(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000018", "IPI annotations require a With/From entry", FailMode.SOFT)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        evidence = str(annotation.evidence.type)
        withfrom = annotation.evidence.with_support_from

        if evidence == "ECO:0000353":
            return self._result(bool(withfrom))
        else:
            return self._result(True)


class GoRule26(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000026", "IBA evidence codes should be filtered from main MOD gaf sources", FailMode.HARD)
        self.offending_evidence = ["ECO:0000318"]

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        evidence = str(annotation.evidence.type)
        # If we see a bad evidence, and we're not in a paint file then fail.
        fails = (evidence in self.offending_evidence and not config.paint)
        return self._result(not fails)


class GoRule28(RepairRule):
    def __init__(self):
        super().__init__("GORULE:0000028", "Aspect can only be one of C, P, F", FailMode.HARD)
        self.namespace_aspect_map = {
            "biological_process": "P",
            "cellular_component": "C",
            "molecular_function": "F"
        }

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        aspect = annotation.aspect
        goterm = str(annotation.object.id)

        if config.ontology is None:
            return TestResult(ResultType.PASS, self.title, annotation)

        namespaces = [predval for predval in config.ontology.get_graph().nodes.get(goterm, {}).get("meta", {}).get("basicPropertyValues", []) if predval["pred"]=="OIO:hasOBONamespace"]
        # the namespaces expression cascades through the json representation of this
        # ontology using empty dict/list if the key is not present

        if len(namespaces) == 0:
            # If this doesn't exist, then it's fine
            return TestResult(ResultType.PASS, self.title, annotation)

        namespace = namespaces[0]["val"]
        expected_aspect = self.namespace_aspect_map[namespace]

        correct_aspect = expected_aspect == aspect
        annotation.aspect = expected_aspect

        repair_state = None
        if correct_aspect:
            repair_state = RepairState.OKAY
        else:
            repair_state = RepairState.REPAIRED

        return TestResult(repair_result(repair_state, self.fail_mode), self.message(repair_state), annotation)


class GoRule29(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000029", "All IEAs over a year are warned, all IEAs over two are removed", FailMode.HARD)
        self.one_year = datetime.timedelta(days=365)
        self.two_years = datetime.timedelta(days=730)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        evidence = str(annotation.evidence.type)
        date = annotation.date

        now = datetime.datetime.today()

        time_compare_delta_short = self.one_year
        time_compare_delta_long = self.two_years
        time_diff = now - datetime.datetime(int(date.year),
                                            int(date.month),
                                            int(date.day),
                                            0, 0, 0, 0)

        iea = "ECO:0000501"
        if evidence == iea:
            if time_diff > time_compare_delta_long:
                return self._result(False)
            elif time_diff > time_compare_delta_short:
                return TestResult(ResultType.WARNING, self.title, annotation)

        ## Default results we we get here.
        return self._result(True)


class GoRule30(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000030", "Deprecated GO_REFs are not allowed", FailMode.SOFT)

    def _ref_curi_to_id(self, goref) -> str:
        """
        Changes reference IDs in the form of GO_REF:nnnnnnn to goref-nnnnnnn
        """
        return goref.lower().replace("_", "").replace(":", "-")

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        references = annotation.evidence.has_supporting_reference
        for ref in references:
            ref = str(ref)
            # Not allowed is obsolete and GO_PAINT:x
            if ref.startswith("GO_PAINT") or (config.goref_metadata is not None and config.goref_metadata.get(self._ref_curi_to_id(ref), {}).get("is_obsolete", False)):
                return self._result(False)

        return self._result(True)


class GoRule37(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000037", "IBA annotations should ONLY be assigned_by GO_Central and have PMID:21873635 as a reference", FailMode.HARD)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        # If the evidence code is IBA, then (1) the assigned_by field must be GO_Central and (2) the reference field must be PMID:21873635
        evidence = str(annotation.evidence.type)
        references = [str(ref) for ref in annotation.evidence.has_supporting_reference]
        assigned_by = annotation.provided_by

        result = self._result(True) # By default we pass
        if evidence == "ECO:0000318":
            result = self._result(assigned_by == "GO_Central" and "PMID:21873635" in references)

        return result


class GoRule39(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000039", "Protein complexes can not be annotated to GO:0032991 (protein-containing complex) or its descendants", FailMode.HARD)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        # An implementation note: This is done by testing if the DB (column 1) is ComplexPortal.
        # This will grab a subset of all actual Protein Complexes. This is noted in the rule description
        db = annotation.subject.id.namespace
        goterm = str(annotation.object.id)

        fails = (db == "ComplexPortal" and goterm == "GO:0032991")
        return self._result(not fails)


class GoRule42(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000042", "Qualifier: IKR evidence code requires a NOT qualifier", FailMode.HARD)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        evidence = str(annotation.evidence.type)

        result = self._result(True)
        ikr = "ECO:0000320"
        if evidence == ikr:
            result = self._result(annotation.negated)

        return result


class GoRule43(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000043", "Check for valid combination of evidence code and GO_REF", FailMode.SOFT)
        self.ecomapping = ecomap.EcoMap()

    def _ref_curi_to_id(self, goref) -> str:
        """
        Changes reference IDs in the form of GO_REF:nnnnnnn to goref-nnnnnnn
        """
        return goref.lower().replace("_", "").replace(":", "-")

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        if config.goref_metadata is None:
            return self._result(True)

        references = [str(ref) for ref in annotation.evidence.has_supporting_reference]
        evidence = str(annotation.evidence.type)

        for ref in references:
            allowed_eco = config.goref_metadata.get(self._ref_curi_to_id(ref), {}).get("evidence_codes", None)
            # allowed_eco are ECO curies
            # allowed_eco will only not be none if the ref was GO_REF:nnnnnnn, that's the only time we care here
            if allowed_eco:
                if evidence not in allowed_eco:
                    return self._result(False)

        return self._result(True)


class GoRule46(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000046", "The ‘with’ field (GAF column 8) must be the same as the gene product (GAF colummn 2) when annotating to ‘self-binding’ terms", FailMode.SOFT)
        self.self_binding_roots = ["GO:0042803", "GO:0051260", "GO:0051289", "GO:0070207", "GO:0043621", "GO:0032840"]
        self.self_binding_terms = None

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        if config.ontology is not None and self.self_binding_terms is None:
            all_terms = []
            # Initialize the self_binding terms if we have an ontology and we haven't already initialized the terms
            for binding_root in self.self_binding_roots:
                root_descendants = config.ontology.descendants(binding_root, relations=["subClassOf"], reflexive=True)
                all_terms += root_descendants

            self.self_binding_terms = set(all_terms)
        elif config.ontology is None:
            # Make sure if we don't have an ontology we still use the set roots
            self.self_binding_terms = self.self_binding_roots

        withfroms = annotation.evidence.with_support_from
        goterm = str(annotation.object.id)

        if goterm in self.self_binding_terms:
            # Then we're in the self-binding case, and check if object ID is in withfrom
            for conj in withfroms:
                if annotation.subject.id in conj.elements:
                    return self._result(True)

            return self._result(False)

        return self._result(True)


class GoRule50(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000050", "Annotations to ISS, ISA and ISO should not be self-referential", FailMode.SOFT)
        self.the_evidences = ["ECO:0000250", "ECO:0000247", "ECO:0000266"]

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        # should not have the same identifier in the 'gene product column' (column 2) and in the 'with/from' column
        # (column 8)
        evidence = str(annotation.evidence.type)
        result = self._result(True)
        if evidence in self.the_evidences:
            # Ensure the gp ID is not an entry in withfrom
            for conj in annotation.evidence.with_support_from:
                result = self._result(annotation.subject.id not in conj.elements)

        return result


class GoRule55(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000055", "References should have only one ID per ID space", FailMode.SOFT)

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        found_id_spaces = dict()
        for ref in annotation.evidence.has_supporting_reference:
            if ref.namespace in found_id_spaces:
                return self._result(False)
            else:
                found_id_spaces[ref.namespace] = ref
        # We found no duplicate IDs, so we good
        return self._result(True)


class GoRule57(GoRule):

    def __init__(self):
        super().__init__("GORULE:0000057", "Group specific filter rules should be applied to annotations", FailMode.HARD, tags=["context-import"])

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        # Check group_metadata is present
        if config.group_metadata is None:
            return self._result(True)

        evidence_codes = config.group_metadata.get("filter_out", {}).get("evidence", [])
        if str(annotation.evidence.type) in evidence_codes:
            return self._result(False)

        evidences_references = config.group_metadata.get("filter_out", {}).get("evidence_reference", [])
        for er in evidences_references:
            evidence_code = er["evidence"]
            reference = er["reference"]
            if str(annotation.evidence.type) == evidence_code and [str(ref) for ref in annotation.evidence.has_supporting_reference] == [reference]:
                return self._result(False)

        properties = config.group_metadata.get("filter_out", {}).get("annotation_properties", [])
        for p in properties:
            if p in annotation.properties.keys():
                return self._result(False)

        return self._result(True)


class GoRule58(RepairRule):

    def __init__(self):
        super().__init__("GORULE:0000058", "Object extensions should conform to the extensions-patterns.yaml "
                                           "file in metadata", FailMode.HARD, tags=["context-import"])

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:

        if config.extensions_constraints is None:
            return TestResult(ResultType.PASS, self.title, annotation)

        if config.ontology is None:
            return TestResult(ResultType.PASS, self.title, annotation)

        repair_state = RepairState.OKAY

        bad_conjunctions = []
        for con in annotation.object_extensions:
            # Count each extension unit, represented by tuple (Relation, Namespace)
            extension_counts = collections.Counter([(str(unit.relation), unit.term.namespace) for unit in con.elements])

            matches = self._do_conjunctions_match_constraint(con, annotation.object.id, config.extensions_constraints, extension_counts)
            # If there is a match in the constraints, then we're all good and we can exit with a pass!
            if not matches:
                bad_conjunctions.append(con)
                repair_state = RepairState.REPAIRED

        repaired_annotation = copy.deepcopy(annotation)
        for con in bad_conjunctions:
            # Remove the bad conjunctions as the "repair"
            repaired_annotation.object_extensions.remove(con)

        return TestResult(repair_result(repair_state, self.fail_mode), self.message(repair_state), repaired_annotation)

    """
    This matches a conjunction against the extension constraints passed in through `extensions-constraints.yaml` in go-site.
    The extensions constraints acts as a white list, and as such each extension unit in the conjunction must
    find a match in the constraints list: the extension relation must match a constraint, and if it does, the
    namespace of the extension filler must much an allowed namespace in the constraint, the annotation GO term
    must match one of the classes in 'primary_terms', and possibly a cardinality of (Relation, Namespace) must
    not be violated.

    If such a match is found, then we can move to the next extension unit in the conjunction list. If each extension has
    a match in the constraints then the conjunction passes the test.

    Any extension unit that fails means the entire conjunction fails.
    """
    def _do_conjunctions_match_constraint(self, conjunction, term, constraints, conjunction_counts):
        # Check each extension in the conjunctions
        for ext in conjunction.elements:

            extension_good = False
            for constraint in constraints:
                constraint_relation_uri = association.relations.lookup_label(constraint["relation"])
                ext_relation_uri = curie_util.expand_uri(str(ext.relation))
                if ext_relation_uri == constraint_relation_uri:

                    if (ext.term.namespace in constraint["namespaces"] and str(term) in constraint["primary_terms"]):
                        # If we match namespace and go term, then if we there is a cardinality constraint, check that.
                        if "cardinality" in constraint:
                            cardinality_violations = [(ext, num) for ext, num in dict(conjunction_counts).items() if num > constraint["cardinality"]]
                            extension_good = len(cardinality_violations) == 0
                        else:
                            extension_good = True

                        if extension_good:
                            # If things are good for this extension, break and go to the next one
                            break

            # if we get through all constraints and we found no constraint match for `ext`
            # Then we know that `ext` is wrong, making the whole conjunction wrong, and we can bail here.
            if not extension_good:
                return False

        # If we get to the end of all extensions without failing early, then the conjunction is good!
        return True


class GoRule61(RepairRule):

    def __init__(self):
        super().__init__("GORULE:0000061", "Only certain gene product to term relations are allowed for a given GO term", FailMode.HARD)
        self.protein_containing_complex_descendents = None

        self.allowed_mf = set([association.Curie(namespace="RO", identity="0002327"), association.Curie(namespace="RO", identity="0002326")])
        self.allowed_bp = set([association.Curie("RO", "0002331"), association.Curie("RO", "0002264"),
                            association.Curie("RO", "0004032"), association.Curie("RO", "0004033"), association.Curie("RO", "0002263"),
                            association.Curie("RO", "0004034"), association.Curie("RO", "0004035")])
        self.allowed_cc_complex = set([association.Curie("BFO", "0000050")])
        self.repairable_cc_complex = set([association.Curie("RO", "0002432"), association.Curie("RO", "0001025")])
        self.allowed_cc_other = set([association.Curie("RO", "0001025"), association.Curie("RO", "0002432"), association.Curie("RO", "0002325")])

    def make_protein_complex_descendents_if_not_present(self, ontology: Optional[ontol.Ontology]) -> Set:
        if ontology is not None and self.protein_containing_complex_descendents is None:
            closure = gafparser.protein_complex_sublcass_closure(ontology)
            self.protein_containing_complex_descendents = closure

        return {} if self.protein_containing_complex_descendents is None else self.protein_containing_complex_descendents

    def test(self, annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> TestResult:
        """
        * GO:0003674 "molecular function"
            * Term: GO:0005554 => relation is RO:0002327 "enables" + repair,
            * Term: subclass of GO:0005554 => relations: {RO:0002327 "enables", RO:0002326 "contributes_to"} + filter
        * GO:0008150 "biological process"
            * Term: GO:0008150 => RO:0002331 "involved_in" + repair
            * Term: subclass of GO:0008150 => relations: {RO:0002331 "involved_in", RO:0002264 "acts upstream or within", RO:0004032 "acts upstream of or within, positive effect", RO:0004033 "acts upstream of or within, negative effect", RO:0002263 "acts upstream of", RO:0004034 "acts upstream of, positive effect", RO:0004035 "acts upstream of, negative effect"} + filter
        * GO:0005575 "cellular component"
            * Term: GO:0005575 => relation is RO:0002432 "is_active_in" + repair
            * If term is subclass of `GO:0032991 "protein-containing complex"` with relation one of {RO:0002432 "is_active_in", RO:0001025 "located in"} => relation should be repaired to `BFO:0000050 "part of"`
            * If term is subclass of `GO:0032991` and any other relation, then it should be filtered
            * Term: any other subclass of `GO:0008372` => allowed relations are {`RO:0001025 "located in"`, `RO:0002432 "is_active_in"`, `RO:0002325 "colocalizes_with"`} and other relations repaired to `RO:0001025 "located in"`.
        """
        if config.ontology is None:
            return TestResult(ResultType.PASS, "", annotation)

        term = str(annotation.object.id)
        namespace = config.ontology.obo_namespace(term)
        repair_state = RepairState.OKAY
        relation = annotation.relation
        allowed = set()

        repaired_annotation = annotation
        if term == "GO:0005554":
            enables = association.Curie(namespace="RO", identity="0002327")
            if relation != enables:
                repaired_annotation = copy.deepcopy(annotation)
                repaired_annotation.relation = enables
                repaired_annotation.qualifiers = [enables]
                allowed = set([enables])
                repair_state = RepairState.REPAIRED
        elif namespace == "molecular_function":
            if relation not in self.allowed_mf:
                enables = association.Curie(namespace="RO", identity="0002327")
                repaired_annotation = copy.deepcopy(annotation)
                repaired_annotation.relation = enables
                repaired_annotation.qualifiers = [enables]
                allowed = self.allowed_mf
                repair_state = RepairState.REPAIRED
        elif term == "GO:0008150":
            involved_in = association.Curie(namespace="RO", identity="0002331")
            if relation != involved_in:
                repaired_annotation = copy.deepcopy(annotation)
                repaired_annotation.relation = involved_in
                repaired_annotation.qualifiers = [involved_in]
                allowed = set([involved_in])
                repair_state = RepairState.REPAIRED
        elif namespace == "biological_process":
            acts_upstream_of_or_within = association.Curie("RO", "0002264")
            if relation not in self.allowed_bp:
                repaired_annotation = copy.deepcopy(annotation)
                repaired_annotation.relation = acts_upstream_of_or_within
                repaired_annotation.qualifiers = [acts_upstream_of_or_within]
                allowed = self.allowed_bp
                repair_state = RepairState.REPAIRED
        elif term == "GO:0005575":
            is_active_in = association.Curie(namespace="RO", identity="0002432")
            if relation != is_active_in:
                repaired_annotation = copy.deepcopy(annotation)
                repaired_annotation.relation = is_active_in
                repaired_annotation.qualifiers = [is_active_in]
                allowed = set([is_active_in])
                repair_state = RepairState.REPAIRED
        elif namespace == "cellular_component":
            if term in self.make_protein_complex_descendents_if_not_present(config.ontology):
                part_of = association.Curie(namespace="BFO", identity="0000050")
                if relation not in self.allowed_cc_complex:
                    if relation in self.repairable_cc_complex:
                        repaired_annotation = copy.deepcopy(annotation)
                        repaired_annotation.relation = part_of
                        repaired_annotation.qualifiers = [part_of]
                        allowed = self.allowed_cc_complex
                        repair_state = RepairState.REPAIRED
                    else:
                        # Not repairable to part_of, so filter
                        repaired_annotation = annotation
                        allowed = self.allowed_cc_complex
                        repair_state = RepairState.FAILED
            else:
                located_in = association.Curie(namespace="RO", identity="0001025")
                if relation not in self.allowed_cc_other:
                    repaired_annotation = copy.deepcopy(annotation)
                    repaired_annotation.relation = located_in
                    repaired_annotation.qualifiers = [located_in]
                    allowed = self.allowed_cc_other
                    repair_state = RepairState.REPAIRED
        else:
            # If we reach here, we're in a weird case where a term is not in either
            # of the three main GO branches, or does not have a namespace defined.
            # If this is the case we should just pass along as if the ontology is missing
            return TestResult(repair_result(RepairState.OKAY, self.fail_mode), "{}: {}".format(self.message(repair_state), "GO term has no namespace"), repaired_annotation)

        allowed_str = ", ".join([str(a) for a in allowed])
        return TestResult(repair_result(repair_state, self.fail_mode), "{}: {} should be one of {}".format(self.message(repair_state), relation, allowed_str), repaired_annotation)


GoRules = enum.Enum("GoRules", {
    "GoRule02": GoRule02(),
    "GoRule06": GoRule06(),
    "GoRule07": GoRule07(),
    "GoRule08": GoRule08(),
    "GoRule11": GoRule11(),
    "GoRule15": GoRule15(),
    "GoRule16": GoRule16(),
    "GoRule17": GoRule17(),
    "GoRule18": GoRule18(),
    "GoRule26": GoRule26(),
    "GoRule28": GoRule28(),
    "GoRule29": GoRule29(),
    "GoRule30": GoRule30(),
    "GoRule37": GoRule37(),
    "GoRule39": GoRule39(),
    "GoRule42": GoRule42(),
    "GoRule43": GoRule43(),
    "GoRule46": GoRule46(),
    "GoRule50": GoRule50(),
    "GoRule55": GoRule55(),
    "GoRule57": GoRule57(),
    "GoRule58": GoRule58(),
    "GoRule61": GoRule61(),
    # GoRule13 at the bottom in order to make all other rules clean up an annotation before reaching 13
    "GoRule13": GoRule13()
})


GoRulesResults = collections.namedtuple("GoRulesResults", ["all_results", "annotation"])


def test_go_rules(annotation: association.GoAssociation, config: assocparser.AssocParserConfig, group=None) -> GoRulesResults:
    all_results = {}

    active_annotation = annotation
    for rule in list(GoRules):
        result = rule.value.run_test(active_annotation, config, group=group)
        # Accumulate all repairs performed  by all tests to the annotation
        active_annotation = result.result
        all_results[rule.value] = result

    return GoRulesResults(all_results, active_annotation)
