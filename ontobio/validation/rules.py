import typing
import enum
import io
import collections

from dataclasses import dataclass
from typing import List, TypeVar, Union, Generic, Optional

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
              "instance":
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
              "instance":
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
ExampleType = enum.Enum("ExampleType", ["REPAIR", "FAIL", "PASS"])

@dataclass
class RuleExample:
    rule_id: str
    example_type: ExampleType
    input: str
    format: FormatType
    expected: Union[str, bool]
    
@dataclass
class ValidationResult:
    example: RuleExample
    actual: Union[str, bool]
    success: bool
    reason: str
    
Parsed = collections.namedtuple("Parsed", ["report", "output"])

def normalize_tsv_row(size: int, tsv: str) -> str:
    columns = tsv.split("\t")
    if len(columns) < size:
        columns += [""] * (size - len(columns))
    elif len(columns) > size:
        columns = columns[0:size]
    
    return "\t".join(columns)

def validate_example(example: RuleExample) -> ValidationResult:
    """
    1. Create parser based on `format`
    2. Run input into parser/validator
    3. In parsed rule results, find the results for the rule given in the example
    4. Decide on what the `output` is.
    5. Validate output against the example `expected` to decide on `success`
    6. Consolodate and return `ValidationResult`
    """
    parser = create_base_parser(example.format)
    parsed = validate_input(example.input, parser)
    success = example_success(example, parsed)
    
    actual = len(parsed.report) == 0 if example.example_type in [ExampleType.FAIL, ExampleType.PASS] else parsed.output
    result = ValidationResult(example, actual, success, parsed.report[0]["message"])
    
    
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


def validate_input(input: str, parser: assocparser.AssocParser, config=None) -> Parsed:
    if config:
        parser.config = config
    
    out = []
    writer = assocwriter.GafWriter(file=io.StringIO())
    
    assocs_gen = parser.association_generator(file=io.StringIO(input), skipheader=True)
    for assoc in assocs_gen:
        out.append(writer.tsv_as_string(writer.as_tsv(assoc)))
        
    rules_messages = parser.report.reporter.messages[example.rule_id]
    return Parsed(report=rules_messages, output=out)


def example_success(example: RuleExample, parsed_input: Parsed) -> bool:
    success = False
    if example.example_type == ExampleType.REPAIR:
        success = parsed_input.output == expected.split("\n")
    elif example.example_type in [ ExampleType.FAIL, ExampleType.PASS ]:
        passed_rule = len(parsed_input.report) == 0
        success = passed_rule == example.expected
    
    return success
