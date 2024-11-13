import io
from pathlib import Path
from pprint import pprint
from ontobio.io import assocparser
from ontobio.io import gafparser
from ontobio.io import gpadparser
from ontobio.io import assocwriter


def test_gpad_extension_relation_writing():
    """
    Test the writing of a GPAD file with extension relations using relations.py dict.

    https://github.com/geneontology/pipeline/issues/397
    """
    out = io.StringIO()
    parser = gpadparser.GpadParser()
    parser.config = assocparser.AssocParserConfig(
        paint=True
    )
    writer = assocwriter.GpadWriter(file=out, version="2.0")

    base_path = Path(__file__).parent / "resources"

    # single_relation.gpad is a one line GPAD file in 1.2 format
    gpad_1_2_input_path = base_path / "single_relation.gpad"

    for assoc in parser.association_generator(skipheader=True, file=open(gpad_1_2_input_path)):
        writer.write_assoc(assoc)
        for object_extension_unit in assoc.object_extensions:
            for element in object_extension_unit.elements:
                if str(element.relation).startswith("RO"):
                    pprint(element)
                    assert str(element.relation) != "RO:0002449"

    outlines = out.getvalue().split("\n")

    assert outlines[0] == "!gpad-version: 2.0"
    assert outlines[1] == "!generated-by: GOC"
    assert outlines[2].startswith("!date-generated:")
    assert outlines[3] == "UniProtKB:P46934\t\tRO:0002327\tGO:0004842\tPMID:17996703\tECO:0000315\t\t\t2018-05-01\tWB\tBFO:0000050(GO:0006511),BFO:0000050(GO:0006974),BFO:0000066(GO:0005634),RO:0002233(UniProtKB:P24928),RO:0002630(GO:0001055)\tmodel-state=production|noctua-model-id=gomodel:5323da1800000002|contributor=https://orcid.org/0000-0002-1706-4196"


def test_gpad_iba_writing():
    out = io.StringIO()
    parser = gafparser.GafParser()
    parser.config = assocparser.AssocParserConfig(
        paint=True
    )
    writer = assocwriter.GpadWriter(file=out, version="1.2")

    base_path = Path(__file__).parent / "resources"

    # Define the paths for the GAF and expected GPI file
    gaf_path = base_path / "wb_single_iba.gaf"
    for assoc in parser.association_generator(skipheader=True, file=open(gaf_path)):
        writer.write_assoc(assoc)

    outlines = out.getvalue().split("\n")

    print(outlines)
    assert outlines[0] == "!gpa-version: 1.2"
    assert outlines[1] == "!generated-by: GOC"
    assert outlines[2].startswith("!date-generated:")
    assert outlines[3] == "WB\tWBGene00022144\tpart_of\tGO:0005886\tPMID:21873635\tECO:0000318\tPANTHER:PTN000073732|RGD:3252\t\t20180308\tGO_Central\t\t"

