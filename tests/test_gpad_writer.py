import io
from ontobio.io import assocparser
from ontobio.io import gafparser
from ontobio.io import assocwriter


def test_gpad_iba_writing():
    out = io.StringIO()
    parser = gafparser.GafParser()
    parser.config = assocparser.AssocParserConfig(
        paint=True
    )
    writer = assocwriter.GpadWriter(file=out)

    for assoc in parser.association_generator(skipheader=True, file=open("tests/resources/wb_single_iba.gaf")):
        writer.write_assoc(assoc)

    outlines = out.getvalue().split("\n")

    print(outlines)
    assert outlines[0] == "!gpad-version: 1.2"
    assert outlines[1] == "!generated-by: GO Central"
    assert outlines[2].startswith("!date-generated:")
    assert outlines[3] == "WB\tWBGene00022144\tpart_of\tGO:0005886\tPMID:21873635\tECO:0000318\tPANTHER:PTN000073732|RGD:3252\t\t20180308\tGO_Central\t\t"

