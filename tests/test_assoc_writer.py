from ontobio.io import assocwriter

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
        "subject_extensions": ["UniProtKB:P12345"],
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

    expected = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896\t20150305\tPomBase\tfoo(X:1)\tUniProtKB:P12345"
    writer.write_assoc(association)
    gaf = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert expected == gaf
