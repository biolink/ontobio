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
@pytest.mark.slow
def runner():
    return CliRunner()


@pytest.fixture()
@pytest.mark.slow
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


@pytest.fixture(params=[("goa_cow", "goa"), ("goa_chicken", "goa"), ("mgi", "MGI"), ("zfin", "ZFIN")], scope='session')
@pytest.mark.slow
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

    zipped_gaf = Path(__file__).parent / "groups" / group / f"{dataset}.gaf.gz"
    assert os.path.exists(zipped_gaf)
    return dataset, group, metadata


@pytest.mark.slow
def test_validate_resulting_gaf(gaf_setup):
    dataset = gaf_setup[0]
    group = gaf_setup[1]
    base_path = Path(__file__).parent / "resources"
    ontology = "go"
    ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)
    metadata = base_path / "metadata"
    datasets = metadata / "datasets"
    assert os.path.exists(datasets)
    assert os.path.exists(metadata)

    gaf_parser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    zipped_gaf = Path(__file__).parent / "groups" / group / f"{dataset}.gaf.gz"

    assert os.path.exists(zipped_gaf)
    unzipped_gaf = Path(__file__).parent / "groups" / group / f"{dataset}.gaf"
    results = gaf_parser.parse(unzipped_gaf)
    assert len(results) > 0
    print(metadata)


@pytest.mark.slow
def test_validate_gaf():
    dataset = "goa_chicken"
    group = "goa"
    ontology_graph = OntologyFactory().create("go", ignore_cache=True)
    gaf_parser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    gpad_parser = GpadParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))
    zipped_gaf = Path(__file__).parent / "groups" / group / f"{dataset}.gaf.gz"

    assert os.path.exists(zipped_gaf)

    unzipped_gaf = str(Path(__file__).parent / "groups" / group / f"{dataset}.gaf")
    assert os.path.exists(unzipped_gaf)
    assert os.path.exists(Path(__file__).parent / "groups" / group / f"{dataset}.gpad")
    gpad_results = gpad_parser.parse(str(Path(__file__).parent / "groups" / group / f"{dataset}.gpad"))
    results = gaf_parser.parse(unzipped_gaf)
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

