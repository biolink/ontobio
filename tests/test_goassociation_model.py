from ontobio.model import association
from ontobio.io import gafparser
from ontobio.io import gpadparser

def test_negated_qualifers():

    gaf = ["PomBase", "SPBC11B10.09", "cdc2", "NOT", "GO:0007275", "PMID:21873635", "IBA", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    association = gafparser.to_association(gaf).associations[0]
    to_gaf = association.to_gaf_tsv()
    assert to_gaf[3] == "NOT"

    to_gpad = association.to_gpad_tsv()
    assert to_gpad[2] == "NOT"

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
    assert c == [association.ConjunctiveSet(["MGI:12345"])]

    c = association.ConjunctiveSet.str_to_conjunctions("MGI:12345,MGI:12345")
    assert c == [association.ConjunctiveSet(["MGI:12345", "MGI:12345"])]

    c = association.ConjunctiveSet.str_to_conjunctions("MGI:12345|MGI:12345")
    assert c == [association.ConjunctiveSet(["MGI:12345"]), association.ConjunctiveSet(["MGI:12345"])]

    c = association.ConjunctiveSet.str_to_conjunctions("MGI:12345,DOI:333|GO:987")
    assert c == [
            association.ConjunctiveSet(["MGI:12345", "DOI:333"]),
            association.ConjunctiveSet(["GO:987"])
        ]

    c = association.ConjunctiveSet.str_to_conjunctions("part_of(MGI:123),part_of(FOO:456)|has_direct_input(BAR:987)", conjunct_element_builder=lambda u: association.ExtensionUnit.from_str(u))
    assert c == [
            association.ConjunctiveSet([association.ExtensionUnit("part_of", "MGI:123"), association.ExtensionUnit("part_of", "FOO:456")]),
            association.ConjunctiveSet([association.ExtensionUnit("has_direct_input", "BAR:987")])
        ]

    c = association.ConjunctiveSet.str_to_conjunctions("HECK_NO,part_of(FOO:456)|has_direct_input(BAR:987)", conjunct_element_builder=lambda u: association.ExtensionUnit.from_str(u))
    assert c == association.Error("HECK_NO")

def test_conjunctive_set_list_to_str():
    c = association.ConjunctiveSet.list_to_str([])
    assert c == ""

    c = association.ConjunctiveSet.list_to_str([association.ConjunctiveSet(["MGI:12345"])])
    assert c == "MGI:12345"

    c = association.ConjunctiveSet.list_to_str([association.ConjunctiveSet(["MGI:12345", "MGI:12345"])])
    assert c == "MGI:12345,MGI:12345"

    c = association.ConjunctiveSet.list_to_str([association.ConjunctiveSet(["MGI:12345"]), association.ConjunctiveSet(["MGI:12345"])])
    assert c == "MGI:12345|MGI:12345"

    c = association.ConjunctiveSet.list_to_str([
            association.ConjunctiveSet(["MGI:12345", "DOI:333"]),
            association.ConjunctiveSet(["GO:987"])
        ])
    assert c == "MGI:12345,DOI:333|GO:987"
