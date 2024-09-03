from pathlib import Path

import pytest
from click.testing import CliRunner
from bin.validate import produce
import os
import requests

from ontobio import OntologyFactory
from ontobio.io import assocparser
from ontobio.io.gafparser import GafParser
from ontobio.io.gpadparser import GpadParser


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture()
def go_json():
    url = 'http://snapshot.geneontology.org/ontology/go-basic.json'
    file_path = os.path.join(os.getcwd(), 'go-basic.json')
    response = requests.get(url)
    if response.status_code == 200:
        with open(file_path, 'wb') as f:
            f.write(response.content)
    else:
        pytest.fail(f'Failed to download file: {url} with status code: {response.status_code}')

    return file_path


@pytest.mark.slow
def test_slow_function():
    import time
    time.sleep(10)  # Simulate a slow test
    assert True


def test_fast_function():
    assert True


datasets_to_test = [("zfin", "ZFIN"), ("fb", "FlyBase"), ("mgi", "MGI"), ("rgd", "RGD"), ("goa", "goa-chicken")]


# Test function that uses the fixtures
@pytest.mark.parametrize("dataset,group", [("ZFIN", "zfin")])
@pytest.mark.slow
def test_gaf_setup(dataset, group, runner, go_json):
    # Ensure that the required files are created
    base_path = Path(__file__).parent / "resources"
    metadata = base_path / "metadata"
    assert os.path.exists(metadata), f"Metadata directory does not exist: {metadata}"
    assert os.path.exists(go_json), f"go-basic.json file does not exist: {go_json}"

    result = runner.invoke(produce, [
        '-m', metadata,
        '--gpad',
        '-t', '.',
        '-o', 'go-basic.json',
        '--base-download-url', 'http://skyhook.berkeleybop.org/snapshot/',
        '--only-dataset', group, dataset,
        '--gpad-gpi-output-version', '2.0'
    ])

    print(f"Exit Code: {result.exit_code}")
    print(f"Standard Output: {result.stdout}")
    assert result.exit_code == 0, f"Command failed with exit code {result.exit_code}. Stderr: {result.stderr}"

    assert os.path.exists(Path(__file__).parent.parent / "groups" / group)

    zipped_gaf = Path(__file__).parent.parent / "groups" / group / f"{dataset}.gaf.gz"
    print(zipped_gaf)
    assert os.path.exists(zipped_gaf)

    base_path = Path(__file__).parent / "resources"
    ontology = "go"
    ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)
    metadata = base_path / "metadata"
    datasets = metadata / "datasets"
    assert os.path.exists(datasets)
    assert os.path.exists(metadata)

    gaf_parser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    zipped_gaf = Path(__file__).parent.parent / "groups" / group / f"{dataset}.gaf.gz"
    print(zipped_gaf)

    assert os.path.exists(zipped_gaf)
    unzipped_gaf = Path(__file__).parent.parent / "groups" / group / f"{dataset}.gaf"

    assert os.path.exists(unzipped_gaf)

    # Open the GAF file and pass the file object to the parser
    with unzipped_gaf.open('r') as gaf_file:
        results = gaf_parser.parse(gaf_file)

    assert len(results) > 0
    print(metadata)


@pytest.mark.slow
def test_validate_gaf():
    dataset = "ZFIN"
    group = "zfin"
    ontology_graph = OntologyFactory().create("go", ignore_cache=True)
    gaf_parser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    gpad_parser = GpadParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    zipped_gaf = Path(__file__).parent.parent / "groups" / group / f"{dataset}.gaf.gz"
    print(zipped_gaf)
    assert os.path.exists(zipped_gaf)

    unzipped_gaf = Path(__file__).parent.parent / "groups" / group / f"{dataset}.gaf"
    gpad_path = Path(__file__).parent.parent / "groups" / group / f"{dataset}.gpad"

    assert os.path.exists(unzipped_gaf)
    assert os.path.exists(gpad_path)

    # Open the GPAD file and parse
    with gpad_path.open('r') as gpad_file:
        gpad_results = gpad_parser.parse(gpad_file)

    # Open the GAF file and parse
    with unzipped_gaf.open('r') as gaf_file:
        results = gaf_parser.parse(gaf_file)

    assert gaf_parser.version == "2.2"
    assert len(results) > 0
    for result in results:
        if hasattr(result, 'subject'):
            assert not result.subject.id.namespace == "PR"

    assert gpad_parser.version == '2.0'
    assert len(gpad_results) > 0
    for gpad_result in gpad_results:
        if hasattr(gpad_result, 'subject'):
            assert not gpad_result.subject.id.namespace == "PR"

