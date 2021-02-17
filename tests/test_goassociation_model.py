import pytest

from ontobio.model import association
from ontobio.model.association import Curie
from ontobio.io import gafparser

def test_negated_qualifiers():

    gaf = ["PomBase", "SPBC11B10.09", "cdc2", "NOT", "GO:0007275", "PMID:21873635", "IBA", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    association = gafparser.to_association(gaf).associations[0]
    to_gaf = association.to_gaf_2_1_tsv()
    assert to_gaf[3] == "NOT"

    to_gpad = association.to_gpad_1_2_tsv()
    assert to_gpad[2] == "NOT|involved_in"

def test_conjunctiveset_tostring():
    c = association.ConjunctiveSet(["MGI:12345"])
    assert str(c) == "MGI:12345"

    c = association.ConjunctiveSet(["MGI:12345", "MGI:12345"])
    assert str(c) == "MGI:12345,MGI:12345"

    c = association.ConjunctiveSet([])
    assert str(c) == ""

def test_conjunctive_set_str_to_conjunctions():
    c = association.ConjunctiveSet.str_to_conjunctions("")
    assert c == []

    c = association.ConjunctiveSet.str_to_conjunctions("MGI:12345")
    assert c == [association.ConjunctiveSet([Curie.from_str("MGI:12345")])]

    c = association.ConjunctiveSet.str_to_conjunctions("MGI:12345,MGI:12345")
    assert c == [association.ConjunctiveSet([Curie.from_str("MGI:12345"), Curie.from_str("MGI:12345")])]

    c = association.ConjunctiveSet.str_to_conjunctions("MGI:12345|MGI:12345")
    assert c == [association.ConjunctiveSet([Curie.from_str("MGI:12345")]), association.ConjunctiveSet([Curie.from_str("MGI:12345")])]

    c = association.ConjunctiveSet.str_to_conjunctions("MGI:12345,DOI:333|GO:987")
    assert c == [
            association.ConjunctiveSet([Curie.from_str("MGI:12345"), Curie.from_str("DOI:333")]),
            association.ConjunctiveSet([Curie.from_str("GO:987")])
        ]

    c = association.ConjunctiveSet.str_to_conjunctions("part_of(MGI:123),part_of(FOO:456)|has_direct_input(BAR:987)", conjunct_element_builder=lambda u: association.ExtensionUnit.from_str(u))
    assert c == [
            association.ConjunctiveSet([association.ExtensionUnit(Curie.from_str("BFO:0000050"), Curie.from_str("MGI:123")), association.ExtensionUnit(Curie.from_str("BFO:0000050"), Curie.from_str("FOO:456"))]),
            association.ConjunctiveSet([association.ExtensionUnit(Curie.from_str("GOREL:0000752"), Curie.from_str("BAR:987"))])
        ]

    c = association.ConjunctiveSet.str_to_conjunctions("HECK_NO,part_of(FOO:456)|has_direct_input(BAR:987)", conjunct_element_builder=lambda u: association.ExtensionUnit.from_str(u))
    assert c == association.Error("HECK_NO")

def test_conjunctive_set_list_to_str():
    c = association.ConjunctiveSet.list_to_str([])
    assert c == ""

    c = association.ConjunctiveSet.list_to_str([association.ConjunctiveSet([Curie.from_str("MGI:12345")])])
    assert c == "MGI:12345"

    c = association.ConjunctiveSet.list_to_str([association.ConjunctiveSet([Curie.from_str("MGI:12345"), Curie.from_str("MGI:12345")])])
    assert c == "MGI:12345,MGI:12345"

    c = association.ConjunctiveSet.list_to_str([association.ConjunctiveSet([Curie.from_str("MGI:12345")]), association.ConjunctiveSet([Curie.from_str("MGI:12345")])])
    assert c == "MGI:12345|MGI:12345"

    c = association.ConjunctiveSet.list_to_str([
            association.ConjunctiveSet([Curie.from_str("MGI:12345"), Curie.from_str("DOI:333")]),
            association.ConjunctiveSet([Curie.from_str("GO:987")])
        ])
    assert c == "MGI:12345,DOI:333|GO:987"

def test_date():
    date_str = "20210105"
    date = association.Date(date_str[0:4], date_str[4:6], date_str[6:8], "")
    assert association.ymd_str(date, "-") == "2021-01-05"

def test_subject_fullname():
    s = association.Subject(Curie.from_str("HELLO:12345"), "Hello object", ["fullname"], [], ["protein"], association.Curie.from_str("NCBITaxon:12345"))
    assert "fullname" == s.fullname_field()

    s = association.Subject(Curie.from_str("HELLO:12345"), "Hello object", ["fullname", "another_name"], [], ["protein"], association.Curie.from_str("NCBITaxon:12345"))
    assert "fullname|another_name" == s.fullname_field()

    s = association.Subject(Curie.from_str("HELLO:12345"), "Hello object", ["fullname"], [], ["protein"], association.Curie.from_str("NCBITaxon:12345"))
    assert "fullname" == s.fullname_field(max=1)

def test_subject_types_unknown():
    s = association.Subject(Curie.from_str("HELLO:12345"), "Hello object", ["fullname"], [], [], association.Curie.from_str("NCBITaxon:12345"))
    assert [Curie(namespace="CHEBI", identity="33695")] == s.type

def test_subject_types_label():
    s = association.Subject(Curie.from_str("HELLO:12345"), "Hello object", ["fullname"], [], ["mRNA", "tRNA"], association.Curie.from_str("NCBITaxon:12345"))
    assert [Curie.from_str("SO:0000234"), Curie.from_str("SO:0000253")] == s.type