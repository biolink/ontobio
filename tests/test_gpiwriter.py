import io

from ontobio.io import entitywriter, gafgpibridge


def test_header_newline():
    gpi_obj = {
        'id': "MGI:MGI:1918911",
        'label': "0610005C13Rik",  # db_object_symbol,
        'full_name': "RIKEN cDNA 0610005C13 gene",  # db_object_name,
        'synonyms': [],
        'type': ["SO:0000000"],  # db_object_type,
        'taxon': "NCBITaxon:10090",
        'encoded_by': "", # encoded_by
        'parents': "",
        'protein_containing_complex_members': "", # protein_containing_complex_members
        'xrefs': "",
        'properties': ""

    }

    entity = gafgpibridge.Entity(gpi_obj)

    out = io.StringIO()
    gpiwriter = entitywriter.GpiWriter(file=out)
    gpiwriter.write_entity(entity)
    outlines = out.getvalue().split("\n")

    expected_lines = [
        "!gpi-version: 2.0",
        "MGI:1918911\t0610005C13Rik\tRIKEN cDNA 0610005C13 gene\t\tSO:0000000\tNCBITaxon:10090\t\t\t\t\t",
        ""
    ]
    assert expected_lines == outlines
