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


@pytest.mark.slow
@pytest.mark.parametrize("group, dataset", [
    ("goa_chicken", "goa"),
    ("zfin", "ZFIN")
])
def test_produce_with_required_options(runner, go_json, group, dataset):
    # Ensure that the required files are created
    base_path = Path(__file__).parent / "resources"
    metadata = base_path / "metadata"
    datasets = metadata / "datasets"
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
    assert os.path.exists(Path(__file__).parent / "groups" / group)

    gaf_parser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    zipped_gaf = Path(__file__).parent / "groups" / group / f"{group}.gaf.gz"

    assert os.path.exists(zipped_gaf)
    unzipped_gaf = Path(__file__).parent / "groups" / group / f"{group}.gaf"
    results = gaf_parser.parse(unzipped_gaf)
    print(results[:10])
    assert len(results) > 0
    assert gaf_parser.version == "2.2"

    print(metadata)

    # Remove the "go-basic.json" file
    json_file = "go-basic.json"
    if os.path.exists(json_file):
        os.remove(json_file)
