import typing
import enum
import io
import collections
import click
import json

from dataclasses import dataclass
from typing import List, Dict, TypeVar, Union, Generic, Optional

from ontobio.validation import metadata
from ontobio.io import assocparser
from ontobio.io import gafparser
from ontobio.io import assocwriter

"""
This module is for centralizing logic related to validating the example data in
GO Rules. Optional data can be included in rules that show exmaples of failing,
passing, or repair type rules for incoming data (either GAF, GPAD, or RDF).

This will first just support GAF for the first pass in all liklihood.

Relavent schema:
```
"examples":
  type: map
    required: false
    mapping:
      "pass":
        type: seq
        required: false
        sequence:
          - type: map
            mapping:
              "comment":
                type: str
                required: true
              "format":
                type: str
                required: true
                enum: ["rdf", "gaf", "gpad"]
              "input":
                type: str
                required: true
      "fail":
        type: seq
        required: false
        sequence:
          - type: map
            mapping:
              "comment":
                type: str
                required: true
              "format":
                type: str
                required: true
                enum: ["rdf", "gaf", "gpad"]
              "input":
                type: str
                required: true
      "repair":
        type: seq
        required: false
        sequence:
          - type: map
            mapping:
              "comment":
                type: str
                required: true
              "format":
                type: str
                required: true
                enum: ["rdf", "gaf", "gpad"]
              "input":
                type: str
                required: true
              "output":
                type: str
                required: true
```

"""
FormatType = enum.Enum("FormatType", ["RDF", "GAF", "GPAD"])
ExampleType = enum.Enum("ExampleType", {"REPAIR": "repair", "FAIL": "fail", "PASS": "fail"})

def format_from_string(format: str) -> Optional[FormatType]:
    if format == "rdf":
        return FormatType.RDF

    if format == "gaf":
        return FormatType.GAF

    if format == "gpad":
        return FormatType.GPAD

    return None

@dataclass
class RuleExample:
    rule_id: str
    example_type: ExampleType
    input: str
    format: FormatType
    expected: Union[str, bool]

    @classmethod
    def example_from_json(RuleExample, rule_json: Dict) -> List:
        """
        This constructs the set of examples to be run from a single GO rule.
        """
        # Returns List of RuleExample
        if "examples" not in rule_json:
            # Bail if we don't have any examples
            return []

        fail_examples = rule_json["examples"].get("fail", [])
        pass_examples = rule_json["examples"].get("pass", [])
        repair_examples = rule_json["examples"].get("repair", [])

        built_examples = [] # type: List[RuleExample]
        ruleid = rule_json["id"].lower().replace(":", "-")
        for ex in fail_examples:
            f = format_from_string(ex["format"]) # type: Optional[FormatType]
            # Expected is False since these are "fail" examples
            built_examples.append(RuleExample(ruleid, ExampleType.FAIL, ex["input"], f, False))

        for ex in pass_examples:
            f = format_from_string(ex["format"]) # type: Optional[FormatType]
            # Expected is True since these are "pass" examples
            built_examples.append(RuleExample(ruleid, ExampleType.PASS, ex["input"], f, True))

        for ex in repair_examples:
            f = format_from_string(ex["format"]) # type: Optional[FormatType]
            # Expected will come from the `output` field
            built_examples.append(RuleExample(ruleid, ExampleType.REPAIR, ex["input"], f, ex["output"]))

        return built_examples

@dataclass
class ValidationResult:
    example: RuleExample
    actual: Union[str, bool]
    success: bool
    reason: str

    def to_json(self) -> Dict:
        return {
            "rule": self.example.rule_id,
            "type": self.example.example_type.value,
            "format": self.example.format.value,
            "input": self.example.input,
            "expected": self.example.expected,
            "actual": self.actual,
            "success": self.success,
            "reason": self.reason
        }

Parsed = collections.namedtuple("Parsed", ["report", "output", "expected"])

#==============================================================================

def normalize_tsv_row(size: int, tsv: str) -> str:
    columns = tsv.split("\t")
    if len(columns) < size:
        columns += [""] * (size - len(columns))
    elif len(columns) > size:
        columns = columns[0:size]

    return "\t".join(columns)


def validate_all_examples(examples: List[RuleExample], config=None) -> List[ValidationResult]:
    results = []
    for ex in examples:
        r = validate_example(ex, config=config)
        results.append(r)

    return results


def validate_example(example: RuleExample, config=None) -> ValidationResult:
    """
    1. Create parser based on `format`
    2. Run input into parser/validator
    3. In parsed rule results, find the results for the rule given in the example
    4. Decide on what the `output` is.
    5. Validate output against the example `expected` to decide on `success`
    6. Consolodate and return `ValidationResult`
    """
    parser = create_base_parser(example.format)
    parsed = validate_input(example, parser, config=config)
    # click.echo(parsed)
    success = example_success(example, parsed)

    actual = len(parsed.report) == 0 if example.example_type in [ExampleType.FAIL, ExampleType.PASS] else parsed.output
    reason = "Valid"
    if not success:
        if example.example_type in [ ExampleType.PASS or ExampleType.FAIL ]:
            reason = "Input was expected to {passfail} {ruleid}, but it did not: {message}".format(passfail=example.example_type.value, ruleid=example.rule_id,
                message="; ".join([m["message"] for m in parsed.report]))
        else:
            reason = "Repair found `{}`, but expected `{}`".format(actual, example.expected)

    result = ValidationResult(example, actual, success, reason)
    return result


def create_base_parser(format: FormatType) -> Optional[assocparser.AssocParser]:
    """
    Make an unconfigured parser based on the format. Only GAF is supported currently.
    """
    parser = None
    if format == FormatType.GAF:
        parser = gafparser.GafParser(config=assocparser.AssocParserConfig())
    else:
        parser = None

    return parser


def validate_input(example: RuleExample, parser: assocparser.AssocParser, config=None) -> Parsed:
    if config:
        parser.config = config

    out = []
    writer = assocwriter.GafWriter(file=io.StringIO())

    assocs_gen = parser.association_generator(file=io.StringIO(example.input), skipheader=True)
    for assoc in assocs_gen:
        out.append(writer.tsv_as_string(writer.as_tsv(assoc)))

    rule_messages = parser.report.reporter.messages.get(example.rule_id, [])
    rule_messages.extend(parser.report.reporter.messages.get("gorule-0000001", []))

    # We have to also parse the expected result if we are in a repair to normalize all the data
    expected_out = []
    if example.example_type == ExampleType.REPAIR:
        expected_parsed_gen = create_base_parser(example.format).association_generator(file=io.StringIO(example.expected), skipheader=True)
        expected_writer = assocwriter.GafWriter(file=io.StringIO())
        for assoc in expected_parsed_gen:
            expected_out.append(expected_writer.tsv_as_string(expected_writer.as_tsv(assoc)))

    # We only collect the messages from *our* rule we're in
    return Parsed(report=rule_messages, output="\n".join(out), expected="\n".join(expected_out))


def example_success(example: RuleExample, parsed_input: Parsed) -> bool:
    """
    Decide if the example was a success. Given the example and the result of parsing
    and validation, this will return True if we expected the example to fail validation/repair
    the rule and it did so or if the example is expected to pass the rule and it did so.
    This returns False if validation produces something we did not expect.

    Additionally, examples will not succeed if we aren't testing rule 1, but still fail rule 1
    """
    success = False
    if example.rule_id != "gorule-0000001" and (1 in [message["rule"] for message in parsed_input.report]):
        # If we find a gorule-0000001 report in a non gorule-0000001 example, than we auto-fail success
        return False

    if example.example_type == ExampleType.REPAIR:
        success = parsed_input.output == parsed_input.expected
    elif example.example_type in [ ExampleType.FAIL, ExampleType.PASS ]:
        # The rule was passed if there were no messages from that rule
        passed_rule = len(parsed_input.report) == 0
        # We have a successful example if the passing above was what we expected give the example
        success = passed_rule == example.expected

    return success

def validation_report(all_results: List[ValidationResult]) -> Dict:
    """
    {
        "gorule-00000008": {
            "results": [
                {
                    "rule": "gorule-00000008"
                    "type": "fail|pass|repair",
                    "format": "gaf|gpad|rdf",
                    "input": "string",
                    "expected": "string|bool",
                    "actual": "string|bool",
                    "success": "bool",
                    "reason": "string"
                }, "..."
            ]
        }
    }
    """
    report_dict = dict()
    for r in all_results:
        if r.example.rule_id not in report_dict:
            report_dict[r.example.rule_id] = []

        r_out = r.to_json()
        report_dict[r.example.rule_id].append(r_out)

    return report_dict
