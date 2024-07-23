from bin import validate
from ontobio.ontol_factory import OntologyFactory
from pprint import pprint

gpi_file = "../tests/resources/mgi.truncated.gpi2"
gaf_file_to_fix = "../tests/resources/mgi.gaf"
output_file_path = "fixed_test.gaf"
ontology = "go"
ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)


def test_fix_isoforms():
    validate.fix_pro_isoforms_in_gaf(gaf_file_to_fix, gpi_file, ontology_graph, output_file_path)
    with open(output_file_path, 'r') as f:
        lines = f.readlines()
    for line in lines:
        assert not line.startswith("PR")
    assert len(lines) > 100

