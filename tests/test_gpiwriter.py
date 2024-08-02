import io
from ontobio.io import entitywriter, gafgpibridge, entityparser
from bin.validate import produce_gpi
from pathlib import Path
import pytest


@pytest.mark.parametrize("gpad_gpi_output_version", ["2.0", "1.2"])
def test_produce_gpi(gpad_gpi_output_version):
    # Base path relative to this script
    base_path = Path(__file__).parent / "resources"

    # Define the paths for the GAF and expected GPI file
    gaf_path = base_path / "mgi.gaf"

    # Ensure the GAF file exists to avoid FileNotFoundError
    if not gaf_path.exists():
        raise FileNotFoundError(f"Expected GAF file does not exist: {gaf_path}")

    # Set parameters for the function
    dataset = "mgi"
    ontology_graph = None  # Assuming setup elsewhere or not needed for this specific test

    # Call the function
    output_gpi_path = produce_gpi(dataset, str(base_path), str(gaf_path), ontology_graph, gpad_gpi_output_version)

    # Convert the output path to a pathlib.Path object for consistency
    output_gpi_path = Path(output_gpi_path)
    assert output_gpi_path.exists(), "The GPI file was not created."

    # Verify the contents of the GPI file
    p = entityparser.GpiParser()
    assert p.parse(open(output_gpi_path, "r")) is not None, "The GPI file could not be parsed."
    results = p.parse(open(output_gpi_path, "r"))
    assert len(results) > 5, "The GPI file should have about 9 unique genes from ~ 90 associations in the GAF file."

    with output_gpi_path.open() as f:
        lines = f.readlines()

    assert len(lines) > 0, "The GPI file should not be empty."


def test_gpi_2_0_writer():
    gpi_obj = {
        'id': "MGI:MGI:1918911",
        'label': "0610005C13Rik",  # db_object_symbol,
        'full_name': "RIKEN cDNA 0610005C13 gene",  # db_object_name,
        'synonyms': [],
        'type': ["gene"],  # db_object_type,
        'taxon': {"id": "NCBITaxon:10090"},
        'encoded_by': "",  # encoded_by
        'parents': "",
        'protein_containing_complex_members': "",  # protein_containing_complex_members
        'xrefs': "",
        'properties': ""
    }

    entity = gafgpibridge.Entity(gpi_obj)

    out = io.StringIO()
    gpiwriter20 = entitywriter.GpiWriter(file=out, version="2.0")
    gpiwriter20.write_entity(entity)
    outlines = out.getvalue().split("\n")

    expected_header_prefixes = [
        "!gpi-version: 2.0",
        "!date-generated:",
        "!generated-by: GOC",
    ]

    print(outlines[1-5])
    for prefix in expected_header_prefixes:
        assert any(line.startswith(prefix) for line in outlines), f"Missing expected header: {prefix}"

    assert "MGI:MGI:1918911\t0610005C13Rik\tRIKEN cDNA 0610005C13 gene\t\tSO:0000704\tNCBITaxon:10090\t\t\t\t\t" in outlines


def test_gpi_1_2_writer():
    gpi_obj = {
        'id': "MGI:MGI:1918911",
        'label': "0610005C13Rik",  # db_object_symbol,
        'full_name': "RIKEN cDNA 0610005C13 gene",  # db_object_name,
        'synonyms': [],
        'type': ["SO:0000000"],  # db_object_type,
        'taxon': {"id": "NCBITaxon:10090"},
        'encoded_by': "",  # encoded_by
        'parents': "",
        'protein_containing_complex_members': "",  # protein_containing_complex_members
        'xrefs': "",
        'properties': ""

    }

    entity = gafgpibridge.Entity(gpi_obj)

    out = io.StringIO()
    gpiwriter20 = entitywriter.GpiWriter(file=out, version="1.2")
    gpiwriter20.write_entity(entity)
    outlines = out.getvalue().split("\n")

    expected_header_prefixes = [
        "!gpi-version: 1.2",
        ""
    ]
    for prefix in expected_header_prefixes:
        assert any(line.startswith(prefix) for line in outlines), f"Missing expected header: {prefix}"

    assert "MGI\tMGI:1918911\t0610005C13Rik\tRIKEN cDNA 0610005C13 gene\t\tSO:0000000\ttaxon:10090\t\t\t" in outlines

