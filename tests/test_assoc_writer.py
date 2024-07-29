from ontobio.io import assocwriter
from ontobio.io import gafparser, gpadparser
from ontobio.model.association import (GoAssociation, Curie, Subject, Term, ConjunctiveSet, Evidence, ExtensionUnit,
                                       Date, Aspect, Provider)
import io


def test_gaf_writer():
    association = GoAssociation(
        source_line="",
        subject=Subject(
            id=Curie("PomBase", "SPAC25B8.17"),
            label="ypf1",
            type=["protein"],
            fullname=["intramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)"],
            synonyms=["ppp81"],
            taxon=Curie("NCBITaxon", "4896")
        ),
        object=Term(
            id=Curie("GO", "0000006"),
            taxon=Curie("NCBITaxon", "4896")
        ),
        negated=False,
        qualifiers=[],
        aspect=Aspect("C"),
        relation=Curie("BFO", "0000050"),
        interacting_taxon=Curie("NCBITaxon", "555"),
        evidence=Evidence(
            type=Curie("ECO", "0000266"),
            has_supporting_reference=[Curie("GO_REF", "0000024")],
            with_support_from=[ConjunctiveSet(
                elements=[Curie("SGD", "S000001583")]
            )]
        ),
        provided_by=Provider("PomBase"),
        date=Date(year="2015", month="03", day="05", time=""),
        subject_extensions=[
            ExtensionUnit(
                relation=Curie("rdfs", "subClassOf"),
                term=Curie("UniProtKB", "P12345")
            )
        ],
        object_extensions=[
            ConjunctiveSet(elements=[
                ExtensionUnit(
                    relation=Curie("BFO", "0000050"),
                    term=Curie("X", "1")
                )
            ])
        ],
        properties=dict()
    )
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)
    # `out` will get written with gaf lines from the above assocation object
    expected = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:4896|taxon:555\t20150305\tPomBase\tpart_of(X:1)\tUniProtKB:P12345"
    writer.write_assoc(association)
    print(out.getvalue())
    gaf = [line.strip("\n") for line in out.getvalue().split("\n") if not line.startswith("!")][0]
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


def test_negated_qualifers():
    gaf = ["PomBase", "SPBC11B10.09", "cdc2", "NOT", "GO:0007275", "PMID:21873635", "ISO", "PANTHER:PTN000623979|TAIR:locus:2099478", "P", "Cyclin-dependent kinase 1", "UniProtKB:P04551|PTN000624043", "protein", "taxon:284812", "20170228", "GO_Central", "", ""]
    parser = gafparser.GafParser()
    result = parser.parse_line("\t".join(gaf))
    writer = assocwriter.GafWriter()
    parsed = writer.as_tsv(result.associations[0])
    print(parsed)
    assert parsed[3] == "NOT"

    writer = assocwriter.GpadWriter()
    parsed = writer.as_tsv(result.associations[0])
    print(parsed)
    assert parsed[2] == "NOT|involved_in"


def test_roundtrip():
    """
    Start with a line, parse it, then write it. The beginning line should be the same as what was written.
    """
    line = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:999|taxon:888\t20150305\tPomBase\tpart_of(X:1)\tUniProtKB:P12345"
    parser = gafparser.GafParser()
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)
    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    gaf = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert line == gaf

    # Single taxon
    line = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:1111\t20150305\tPomBase\tpart_of(X:1)\tUniProtKB:P12345"
    parser = gafparser.GafParser()
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out)
    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    gaf = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert line == gaf


def test_gpad_qualifier_removed_in_gaf_2_1():
    # Qualifier is `part_of` and should be returned blank instead of removing the whole line
    line = "PomBase\tSPBC1348.01\tpart_of\tGO:0009897\tGO_REF:0000051\tECO:0000266\t\t\t20060201\tPomBase\t\t"
    parser = gpadparser.GpadParser()
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out, version="2.1")  # Write out to gaf 2.1

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    gpad_to_gaf_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert gpad_to_gaf_line.split("\t")[3] == ""

    # Test with a `NOT`
    line = "PomBase\tSPBC1348.01\tNOT|part_of\tGO:0009897\tGO_REF:0000051\tECO:0000266\t\t\t20060201\tPomBase\t\t"
    parser = gpadparser.GpadParser()
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out, version="2.1")  # Write out to gaf 2.1

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    gpad_to_gaf_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert gpad_to_gaf_line.split("\t")[3] == "NOT"

def test_gaf2_2_qualifier_to_gaf2_1():
    # Qualifier is `part_of` and should be returned blank instead of removing the whole line
    line = "WB\tWBGene00000001\taap-1\tinvolved_in\tGO:0008286\tWB_REF:WBPaper00005614|PMID:12393910\tIMP\t\tP\t\tY110A7A.10\tgene\ttaxon:6239\t20060302\tWB\t\t"
    parser = gafparser.GafParser()
    parser.version = "2.2"
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out, version="2.1")  # Write out to gaf 2.1

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    gpad_to_gaf_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert gpad_to_gaf_line.split("\t")[3] == ""

    # Test with a `NOT`
    line = "WB\tWBGene00000001\taap-1\tNOT|involved_in\tGO:0008286\tWB_REF:WBPaper00005614|PMID:12393910\tIMP\t\tP\t\tY110A7A.10\tgene\ttaxon:6239\t20060302\tWB\t\t"
    parser = gafparser.GafParser()
    parser.version = "2.2"
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out, version="2.1")  # Write out to gaf 2.1

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    gpad_to_gaf_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert gpad_to_gaf_line.split("\t")[3] == "NOT"

def test_writing_to_gaf_2_2():
    line = "WB\tWBGene00000001\taap-1\tinvolved_in\tGO:0008286\tWB_REF:WBPaper00005614|PMID:12393910\tIMP\t\tP\t\tY110A7A.10\tgene\ttaxon:6239\t20060302\tWB\t\t"
    parser = gafparser.GafParser()
    parser.version = "2.2"
    assoc = parser.parse_line(line).associations[0] # type: GoAssociation

    gaf_22_out = assoc.to_gaf_2_2_tsv()
    assert gaf_22_out[3] == "involved_in"

    # With NOT
    line = "WB\tWBGene00000001\taap-1\tNOT|involved_in\tGO:0008286\tWB_REF:WBPaper00005614|PMID:12393910\tIMP\t\tP\t\tY110A7A.10\tgene\ttaxon:6239\t20060302\tWB\t\t"
    parser = gafparser.GafParser()
    parser.version = "2.2"

    assoc = parser.parse_line(line).associations[0] # type: GoAssociation

    gaf_22_out = assoc.to_gaf_2_2_tsv()
    assert gaf_22_out[3] == "NOT|involved_in"

def test_gaf_2_2_extensions():
    line = "WB\tWBGene00000001\taap-1\tinvolved_in\tGO:0008286\tWB_REF:WBPaper00005614|PMID:12393910\tIMP\t\tP\t\tY110A7A.10\tgene\ttaxon:6239\t20060302\tWB\tpart_of(EMAPA:17972),part_of(CL:0000018)\t"
    parser = gafparser.GafParser()
    parser.version = "2.2"
    assoc = parser.parse_line(line).associations[0]

    gaf_22_out = assoc.to_gaf_2_2_tsv()
    assert gaf_22_out[15] == "part_of(EMAPA:17972),part_of(CL:0000018)"


def test_full_gaf_2_2_write():
    line = "WB\tWBGene00000001\taap-1\tinvolved_in\tGO:0008286\tWB_REF:WBPaper00005614|PMID:12393910\tIMP\t\tP\t\tY110A7A.10\tgene\ttaxon:6239\t20060302\tWB\t\t"
    parser = gafparser.GafParser()
    parser.version = "2.2"
    out = io.StringIO()
    writer = assocwriter.GafWriter(file=out, version="2.2")

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    out_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert out_line.split("\t") == line.split("\t")


def test_gaf_to_gpad2():
    line = "PomBase\tSPAC25B8.17\typf1\t\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:999|taxon:888\t20150305\tPomBase\tpart_of(X:1)\tUniProtKB:P12345"
    parser = gafparser.GafParser()
    out = io.StringIO()
    writer = assocwriter.GpadWriter(version=assocwriter.GPAD_2_0, file=out)

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)

    lines = out.getvalue().split("\n")
    assert lines[0] == "!gpad-version: 2.0"
    assert lines[1] == "!generated-by: GOC"
    assert lines[2].startswith("!date-generated:")
    assert lines[3] == "UniProtKB:P12345\t\tBFO:0000050\tGO:0000006\tGO_REF:0000024\tECO:0000266\tSGD:S000001583\tNCBITaxon:888\t2015-03-05\tPomBase\tBFO:0000050(X:1)\t"

    line = "PomBase\tSPAC25B8.17\typf1\tNOT\tGO:0000006\tGO_REF:0000024\tISO\tSGD:S000001583\tC\tintramembrane aspartyl protease of the perinuclear ER membrane Ypf1 (predicted)\tppp81\tprotein\ttaxon:999|taxon:888\t20150305\tPomBase\tpart_of(X:1)\tUniProtKB:P12345"
    parser = gafparser.GafParser()
    out = io.StringIO()
    writer = assocwriter.GpadWriter(version=assocwriter.GPAD_2_0, file=out)

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)

    lines = out.getvalue().split("\n")
    assert lines[0] == "!gpad-version: 2.0"
    assert lines[1] == "!generated-by: GOC"
    assert lines[2].startswith("!date-generated:")
    assert lines[3] == "UniProtKB:P12345\tNOT\tBFO:0000050\tGO:0000006\tGO_REF:0000024\tECO:0000266\tSGD:S000001583\tNCBITaxon:888\t2015-03-05\tPomBase\tBFO:0000050(X:1)\t"


def test_writing_assoc_properties():
    line = "MGI:MGI:1922721\t\tRO:0002327\tGO:0019904\tMGI:MGI:3769586|PMID:17984326\tECO:0000353\tPR:Q0KK55\t\t2010-12-01\tMGI\tBFO:0000066(EMAPA:17787),RO:0002233(MGI:MGI:1923734)\tcreation-date=2008-02-07|modification-date=2010-12-01|comment=v-KIND domain binding of Kndc1;MGI:1923734|contributor-id=http://orcid.org/0000-0003-2689-5511|contributor-id=http://orcid.org/0000-0003-3394-9805"
    parser = gpadparser.GpadParser()
    parser.version = "2.0"
    out = io.StringIO()
    writer = assocwriter.GpadWriter(file=out, version="2.0")  # Write back out to gpad 2.0

    assoc = parser.parse_line(line).associations[0]
    writer.write_assoc(assoc)
    written_gpad_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    written_props = written_gpad_line.split("\t")[11]
    assert len(written_props.split("|")) == 5


def test_gpad_eco_to_gaf_evidence_code():
    def parse_gpad_vals_to_gaf_io(gpad_vals):
        parser = gpadparser.GpadParser()
        gaf_out = io.StringIO()
        writer = assocwriter.GafWriter(file=gaf_out)

        assoc = parser.parse_line("\t".join(gpad_vals)).associations[0]
        writer.write_assoc(assoc)
        return gaf_out

    vals = [
        "MGI",
        "MGI:88276",
        "is_active_in",
        "GO:0098831",
        "PMID:8909549",
        "ECO:0006003",  # indirectly maps to IDA via gaf-eco-mapping-derived.txt
        "",
        "",
        "20180711",
        "SynGO",
        "part_of(UBERON:0000956)",
        ""
    ]

    out = parse_gpad_vals_to_gaf_io(vals)
    gpad_to_gaf_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert gpad_to_gaf_line.split("\t")[6] == "IDA"

    vals[5] = "ECO:0000314"  # test direct mapping still works
    out = parse_gpad_vals_to_gaf_io(vals)
    gpad_to_gaf_line = [line for line in out.getvalue().split("\n") if not line.startswith("!")][0]
    assert gpad_to_gaf_line.split("\t")[6] == "IDA"
