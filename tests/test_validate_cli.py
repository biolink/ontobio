from pathlib import Path

import pytest
from click.testing import CliRunner
from bin.validate import produce
import os
import requests

from ontobio import OntologyFactory
from ontobio.io import assocparser
from ontobio.io.gafparser import GafParser
ontology = "go"
ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)

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


@pytest.fixture(params=[("goa_chicken", "goa")])
def gaf_setup(request, runner, go_json):
    dataset, group = request.param
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
        '--only-dataset', group,
        dataset,
        '--gpad-gpi-output-version', '2.0'
    ])
    print(result.exit_code)
    print(result.stdout)
    assert os.path.exists(Path(__file__).parent / "groups" / "goa")

    gaf_parser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    zipped_gaf = Path(__file__).parent / "groups" / group / f"{dataset}.gaf.gz"

    assert os.path.exists(zipped_gaf)
    unzipped_gaf = Path(__file__).parent / "groups" / group / f"{dataset}.gaf.gz"
    results = gaf_parser.parse(unzipped_gaf)
    print(results[:10])
    assert len(results) > 0
    assert gaf_parser.version == "2.2"
    print(metadata)


@pytest.mark.slow
def test_validate_resulting_gaf(gaf_setup):
    base_path = Path(__file__).parent / "resources"
    metadata = base_path / "metadata"
    datasets = metadata / "datasets"
