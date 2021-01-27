from ontobio.ecomap import EcoMap
from abc import ABC, abstractmethod
import yaml


class FilterRule(ABC):

    def __init__(self):
        self.id = None
        self.unwanted_evidence_codes = []
        self.unwanted_evi_code_ref_combos = []
        self.required_attributes = []
        self.unwanted_properties = []
        self.load_from_yaml()

    def load_from_yaml(self):
        with open(self.rule_filepath()) as yf:
            rule_ds = yaml.safe_load(yf)

        self.id = rule_ds["id"]

        if rule_ds.get("unwanted_evidence_codes") is not None:
            self.unwanted_evidence_codes = rule_ds["unwanted_evidence_codes"]

        if rule_ds.get("unwanted_evi_code_ref_combos") is not None:
            self.unwanted_evi_code_ref_combos = rule_ds["unwanted_evi_code_ref_combos"]

        if rule_ds.get("required_attributes") is not None:
            self.required_attributes = rule_ds["required_attributes"]
        if self.mod_id():
            self.required_attributes.append({"provided_by": [self.mod_id()]})

        if rule_ds.get("unwanted_properties") is not None:
            self.unwanted_properties = rule_ds["unwanted_properties"]

    @abstractmethod
    def mod_id(self):
        pass

    @abstractmethod
    def rule_filepath(self):
        pass


class DefaultFilterRule(FilterRule):

    def mod_id(self):
        return None

    def rule_filepath(self):
        return "metadata/filter_rules/default.yaml"


class WBFilterRule(FilterRule):
    def mod_id(self):
        return "WB"

    def rule_filepath(self):
        return "metadata/filter_rules/wb.yaml"


class MGIFilterRule(FilterRule):
    def mod_id(self):
        return "MGI"

    def rule_filepath(self):
        return "metadata/filter_rules/mgi.yaml"


def get_filter_rule(mod_id):
    mod_filter_map = {
        'WB': WBFilterRule,
        'MGI': MGIFilterRule
    }
    if mod_id in mod_filter_map:
        return mod_filter_map[mod_id]()
    else:
        return DefaultFilterRule()


class AssocFilter:
    def __init__(self, filter_rule : FilterRule):
        self.filter_rule = filter_rule
        self.ecomap = EcoMap()

    def validate_line(self, assoc):
        evi_code = self.ecomap.ecoclass_to_coderef(assoc["evidence"]["type"])[0]
        if evi_code in self.filter_rule.unwanted_evidence_codes:
            return False
        if len(self.filter_rule.unwanted_evi_code_ref_combos) > 0:
            references = assoc["evidence"]["has_supporting_reference"]
            for evi_ref_combo in self.filter_rule.unwanted_evi_code_ref_combos:
                if evi_ref_combo[0] == evi_code and evi_ref_combo[1] in references:
                    return False
        if len(self.filter_rule.unwanted_properties) > 0 and "annotation_properties" in assoc:
            for up in self.filter_rule.unwanted_properties:
                if up in assoc["annotation_properties"]:
                    return False
        if len(self.filter_rule.required_attributes) > 0:
            meets_requirement = False
            for attr in self.filter_rule.required_attributes:
                # a[attr] is dict
                for k in attr.keys():
                    if assoc[k] in attr[k]:
                        meets_requirement = True
            if not meets_requirement:
                return False
        return True