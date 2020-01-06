from ontobio.validation import rules
from ontobio.io import assocparser
from ontobio.io import gafparser
from ontobio import ontol_factory

import json

ontology = ontol_factory.OntologyFactory().create("tests/resources/goslim_generic.json")
gaf_line = "PomBase\tSPBC11C11.03\tndc80\t\tGO:0000942\tPMID:11553715\tIDA\t\tC\tNMS complex subunit Ndc80\tndc10|tid3\tprotein\ttaxon:4896\t20150122\tPomBase"

def test_create_base_parser():
    parser = rules.create_base_parser(rules.FormatType.RDF)
    assert parser == None

    parser = rules.create_base_parser(rules.FormatType.GAF)
    assert type(parser) == gafparser.GafParser
    assert parser.config == assocparser.AssocParserConfig()

def test_validate_input():
    parser = rules.create_base_parser(rules.FormatType.GAF)
    normal_gaf_line = rules.normalize_tsv_row(17, gaf_line)
    example = rules.RuleExample("gorule-0000027", rules.ExampleType.FAIL, normal_gaf_line, rules.FormatType.GAF, False)
    config = assocparser.AssocParserConfig(
        ontology=ontology
    )

    parsed = rules.validate_input(example, parser, config=config)
    assert parsed.output == normal_gaf_line

def test_example_success_with_fail_example():
    # We expect this example to fail gorule 27, so expected is False
    parser = rules.create_base_parser(rules.FormatType.GAF)
    normalized = rules.normalize_tsv_row(17, gaf_line)
    example = rules.RuleExample("gorule-0000027", rules.ExampleType.FAIL, normalized, rules.FormatType.GAF, False)
    parsed = rules.validate_input(example, parser, config=assocparser.AssocParserConfig(ontology=ontology))

    success = rules.example_success(example, parsed)
    assert success == True

    # We falsely expect rule 1 to pass, so this test is expected to be False
    parser = rules.create_base_parser(rules.FormatType.GAF)
    normalized = rules.normalize_tsv_row(17, gaf_line)
    example = rules.RuleExample("gorule-0000002", rules.ExampleType.FAIL, normalized, rules.FormatType.GAF, False)
    parsed = rules.validate_input(example, parser, config=assocparser.AssocParserConfig(ontology=ontology))

    success = rules.example_success(example, parsed)
    assert success == False

def test_validate_example():
    parser = rules.create_base_parser(rules.FormatType.GAF)
    normalized = rules.normalize_tsv_row(17, gaf_line)
    example = rules.RuleExample("gorule-0000027", rules.ExampleType.FAIL, normalized, rules.FormatType.GAF, False)

    expected = rules.ValidationResult(example, False, True, "Valid")

    config = assocparser.AssocParserConfig(ontology=ontology)
    assert rules.validate_example(example, config=config) == expected

def test_format_parse():

    assert rules.format_from_string("rdf") == rules.FormatType.RDF
    assert rules.format_from_string("gaf") == rules.FormatType.GAF
    assert rules.format_from_string("gpad") == rules.FormatType.GPAD
    assert rules.format_from_string("foo") == None

def test_example_json_converted():

    j = {
        "id": "GORULE:0000027",
        "examples": {
            "fail": [
                {
                    "comment": "an example",
                    "format": "gaf",
                    "input": gaf_line
                }
            ]
        }
    }

    # normalized = rules.normalize_tsv_row(17, gaf_line)
    example = rules.RuleExample("gorule-0000027", rules.ExampleType.FAIL, gaf_line, rules.FormatType.GAF, False)
    assert rules.RuleExample.example_from_json(j) == [example]
