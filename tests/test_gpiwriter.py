import io

from ontobio.io import entitywriter, gafgpibridge


def test_header_newline():
    gpi_obj = {
        'id': "MGI:MGI:1918911",
        'label': "0610005C13Rik",  # db_object_symbol,
        'full_name': "RIKEN cDNA 0610005C13 gene",  # db_object_name,
        'synonyms': [],
        'type': ["gene"],  # db_object_type,
        'parents': "",  # GAF does not have this field, but it's optional in GPI
        'xrefs': "",  # GAF does not have this field, but it's optional in GPI
        'taxon': {
            'id': "NCBITaxon:10090"
        }
    }
    entity = gafgpibridge.Entity(gpi_obj)

    out = io.StringIO()
    gpiwriter = entitywriter.GpiWriter(file=out)
    gpiwriter.write_entity(entity)
    outlines = out.getvalue().split("\n")

    expected_lines = [
        "!gpi-version: 1.2",
        "MGI\tMGI:1918911\t0610005C13Rik\tRIKEN cDNA 0610005C13 gene\t\tgene\ttaxon:10090\t\t\t",
        ""
    ]
    assert expected_lines == outlines
