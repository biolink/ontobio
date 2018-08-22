from ontobio.io import assocparser
from ontobio.io import gafparser

def test_correct_taxon_mapping():
    parser = gafparser.GafParser()
    mapped = parser._taxon_id("taxon:123", assocparser.SplitLine("", [""] * 17, "taxon:123"))

    assert mapped == "NCBITaxon:123"

def test_invalid_mapping():
    parser = gafparser.GafParser()
    mapped = parser._taxon_id("taxon:", assocparser.SplitLine("", [""] * 17, "taxon:"))

    assert mapped == None

def test_already_normalized_mapping():
    parser = gafparser.GafParser()
    mapped = parser._taxon_id("NCBITaxon:123", assocparser.SplitLine("", [""] * 17, "NCBITaxon:123"))

    assert mapped == "NCBITaxon:123"
