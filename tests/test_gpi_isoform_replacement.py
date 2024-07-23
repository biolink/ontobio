from pathlib import Path

from bin import validate
from ontobio.ontol_factory import OntologyFactory
from pprint import pprint

gpi_file = "mgi.truncated.gpi2"
gaf_file_to_fix = "mgi.gaf"
output_file_path = "fixed_test.gaf"
ontology = "go"
ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)


def test_fix_isoforms():
    base_path = Path(__file__).parent / "resources"
    gpi_path = base_path / gpi_file
    # Define the paths for the GAF and expected GPI file
    gaf_path = base_path / gaf_file_to_fix

    # Ensure the GAF file exists to avoid FileNotFoundError
    assert gaf_path.exists()
    assert gpi_path.exists()

    validate.fix_pro_isoforms_in_gaf(str(gaf_path), str(gpi_path), ontology_graph, output_file_path)
    with open(output_file_path, 'r') as f:
        lines = f.readlines()
    for line in lines:
        assert not line.startswith("PR")
    assert len(lines) > 100

