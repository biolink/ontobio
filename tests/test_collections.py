from pathlib import Path

from ontobio.model import collections
from ontobio.model.association import Curie, Subject
from ontobio.io import assocparser, gafparser, gpadparser


def test_bioentities_get_when_empty():
    e = collections.BioEntities(dict())
    assert e.get(Curie("FOO", "123")) == None


def test_bioentities_get_when_exists():
    e = collections.BioEntities({
        Curie("FOO", "123"): Subject(Curie("FOO", "123"), "hello", "world", [], "protien", Curie("NCBITaxon", "12345"))
    })
    assert e.get(Curie.from_str("FOO:123")) == Subject(Curie("FOO", "123"), "hello", "world", [], "protien",
                                                       Curie("NCBITaxon", "12345"))


def test_bioentities_merge():
    e = collections.BioEntities({
        Curie("FOO", "123"): Subject(Curie("FOO", "123"), "hello", "world", [], "protien", Curie("NCBITaxon", "12345"))
    })

    o = collections.BioEntities({
        Curie("BAR", "987"): Subject(Curie("BAR", "987"), "goodbye", "world", [], "protien", Curie("NCBITaxon", "999"))
    })

    assert e.merge(o) == collections.BioEntities({
        Curie("FOO", "123"): Subject(Curie("FOO", "123"), "hello", "world", [], "protien", Curie("NCBITaxon", "12345")),
        Curie("BAR", "987"): Subject(Curie("BAR", "987"), "goodbye", "world", [], "protien", Curie("NCBITaxon", "999"))
    })

    # Test that blank label does not overwrite existing label
    p = collections.BioEntities({
        Curie("BAR", "987"): Subject(Curie("BAR", "987"), "", "world", [], "protien", Curie("NCBITaxon", "999"))
    })

    assert o.merge(p) == collections.BioEntities({
        Curie("BAR", "987"): Subject(Curie("BAR", "987"), "goodbye", "world", [], "protien", Curie("NCBITaxon", "999"))
    })


def test_bioentities_merge_clobber():
    e = collections.BioEntities({
        Curie("FOO", "123"): Subject(Curie("FOO", "123"), "hello", "world", [], "protien", Curie("NCBITaxon", "12345"))
    })

    o = collections.BioEntities({
        Curie("FOO", "123"): Subject(Curie("FOO", "123"), "different", "world", [], "dog", Curie("NCBITaxon", "12345"))
    })
    # Get the clobbered key, the value should be the subject in `o`
    assert e.merge(o).get(Curie("FOO", "123")) == Subject(Curie("FOO", "123"), "different", "world", [], "dog",
                                                          Curie("NCBITaxon", "12345"))


def test_bioentities_load_from_file():
    pombase = collections.BioEntities.load_from_file("tests/resources/truncated-pombase.gpi")
    assert len(pombase.entities.keys()) == 199  # Has 199 gpi lines in the file
    assert pombase.get(Curie.from_str("PomBase:SPAC1565.04c")) == Subject(Curie.from_str("PomBase:SPAC1565.04c"),
                                                                          "ste4", ["adaptor protein Ste4"], [],
                                                                          ["protein"], Curie.from_str("NCBITaxon:4896"))


def test_bioentities_file_gone():
    gone = collections.BioEntities.load_from_file("not_here.gpi")
    assert gone.entities == dict()


def test_create_parser_non_version_line():
    parser = collections.create_parser_from_header("! hello", assocparser.AssocParserConfig())
    assert parser == None


def test_create_parser_gaf():
    parser = collections.create_parser_from_header("!gaf-version: 2.1", assocparser.AssocParserConfig())
    assert isinstance(parser, gafparser.GafParser)
    assert parser.version == "2.1"

    parser = collections.create_parser_from_header("!gaf-version: 2.2", assocparser.AssocParserConfig())
    assert isinstance(parser, gafparser.GafParser)
    assert parser.version == "2.2"


def test_create_parser_gpad():
    parser = collections.create_parser_from_header("!gpa-version: 1.2", assocparser.AssocParserConfig())
    assert isinstance(parser, gpadparser.GpadParser)
    assert parser.version == "1.2"

    parser = collections.create_parser_from_header("!gpad-version: 2.0", assocparser.AssocParserConfig())
    assert isinstance(parser, gpadparser.GpadParser)
    assert parser.version == "2.0"


def test_construct_collection_empty():
    collection = collections.construct_collection(None, [], assocparser.AssocParserConfig())
    assert collection.headers == []
    assert collection.associations == collections.GoAssociations([])
    assert collection.entities == collections.BioEntities(dict())


def test_construct_collection_basic():
    collection = collections.construct_collection("tests/resources/truncated-pombase.gaf",
                                                  ["tests/resources/truncated-pombase.gpi"],
                                                  assocparser.AssocParserConfig())
    # There are 24 lines of headers in the truncated-pombase.gaf
    assert len(collection.headers) == 25
    # There are many lines in this file, we should get more than 100 back
    assert len(collection.associations.associations) > 100
    # This is a 199 line gpi file, with each identifier unique, so should have 200 entity entries
    assert len(collection.entities.entities.keys()) == 199


def test_construct_collection_no_version_error():
    collection = collections.construct_collection("tests/resources/no-version.gaf", [], assocparser.AssocParserConfig())
    assert collection.associations.associations == []
    assert collection.report.to_report_json()["messages"]["gorule-0000001"][0]["type"] == "Invalid Annotation File"


def test_bioentities_from_gpi_2_0():
    base_path = Path(__file__).parent / "resources"
    gpi_path = base_path / "mgi.truncated.gpi2"
    entities = collections.BioEntities.load_from_file(str(gpi_path))
    assert entities.get(Curie(namespace="MGI", identity="MGI:1918925")) == Subject(
        id=Curie.from_str("MGI:MGI:1918925"),
        label="Sanbr",
        fullname=["SANT and BTB domain regulator of CSR"],
        synonyms=["0610010F05Rik"],
        type=[Curie(namespace='SO', identity='0001217')],
        taxon=Curie(namespace="NCBITaxon", identity="10090"),
        db_xrefs=[Curie(namespace='UniProtKB', identity='Q68FF0')])
