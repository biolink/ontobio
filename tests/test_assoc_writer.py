from ontobio.io import assocwriter
from ontobio.io import gafparser
import json
import io

def test_empty_extension_expression():
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    extension = writer._extension_expression({})
    assert extension == ""

def test_single_entry_extension():
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    expression = {
        "union_of": [
            {
                "intersection_of": [
                    {
                        "property": "foo",
                        "filler": "X:1"
                    }
                ]
            }
        ]
    }

    extension = writer._extension_expression(expression)
    assert "foo(X:1)" == extension

def test_unions_extension():
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    expression = {
        "union_of": [
            {
                "intersection_of": [
                    {
                        "property": "foo",
                        "filler": "X:1"
                    }
                ]
            },
            {
                "intersection_of": [
                    {
                        "property": "bar",
                        "filler": "Y:1"
                    }
                ]
            }
        ]
    }

    extension = writer._extension_expression(expression)
    assert "foo(X:1)|bar(Y:1)" == extension

def test_intersection_extensions():
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    expression = {
        "union_of": [
            {
                "intersection_of": [
                    {
                        "property": "foo",
                        "filler": "X:1"
                    },
                    {
                        "property": "foo",
                        "filler": "X:2"
                    }
                ]
            },
            {
                "intersection_of": [
                    {
                        "property": "bar",
                        "filler": "Y:1"
                    }
                ]
            }
        ]
    }

    extension = writer._extension_expression(expression)
    assert "foo(X:1),foo(X:2)|bar(Y:1)" == extension

def test_gaf_writer():
    association = {
        "subject": {
            "id": "PomBase:SPAC25B8.17",
            "label": "ypf1",
            "type": "protein",
            "fullname": "intramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)",
            "synonyms": [
                "ppp81"
            ],
            "taxon": {
                "id": "NCBITaxon:4896"
            }
        },
        "object": {
            "id": "GO:0000006",
            "taxon": "NCBITaxon:4896"
        },
        "negated": False,
        "qualifiers": [],
        "aspect": "C",
        "relation": {
            "id": "part_of"
        },
        "interacting_taxon": "NCBITaxon:555",
        "evidence": {
            "type": "ISO",
            "has_supporting_reference": [
                "GO_REF:0000024"
            ],
            "with_support_from": [
                "SGD:S000001583"
            ]
        },
        "provided_by": "PomBase",
        "date": "20150305",
        "subject_extensions": [
            {
                "property": "isoform",
                "filler": "UniProtKB:P12345"
            }
        ],
        "object_extensions": {
            "union_of": [
                {
                    "intersection_of": [
                        {
                            "property": "foo",
                            "filler": "X:1"
                        }
                    ]
                }
            ]
        }
    }
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    expected = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896|taxon:555\t20150305\tPomBase\tfoo(X:1)\tUniProtKB:P12345"
    writer.write_assoc(association)
    gaf = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert expected == gaf

def test_full_taxon_field_single_taxon():
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    taxon_field = writer._full_taxon_field("taxon:12345", None)
    assert "taxon:12345" == taxon_field

def test_full_taxon_field_interacting():
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    taxon_field = writer._full_taxon_field("taxon:12345", "taxon:6789")
    assert "taxon:12345|taxon:6789" == taxon_field

def test_full_taxon_empty_string_interacting_taxon():
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)

    taxon_field = writer._full_taxon_field("taxon:12345", "")
    assert "taxon:12345" == taxon_field

def test_roundtrip():
    """
    Start with a line, parse it, then write it. The beginning line should be the same as what was written.
    """
    line = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:999|taxon:888\t20150305\tPomBase\tfoo(X:1)\tUniProtKB:P12345"
    parser = gafparser.GafParser()
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)
    assoc_dict = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc_dict)
    gaf = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert line == gaf

    # Single taxon
    line = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:1111\t20150305\tPomBase\tfoo(X:1)\tUniProtKB:P12345"
    parser = gafparser.GafParser()
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)
    assoc_dict = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc_dict)
    gaf = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert line == gaf
