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


# (dataset, group) tuples, adjust as needed for full testing
datasets_to_test = [
    # ("zfin", "zfin"),
    # ("mgi", "mgi"),
    ("goa_cow", "goa"),
    # ("cgd", "cgd"),
    # ("tair", "tair"),
]


# Test function that uses the fixtures

@pytest.mark.slow
def test_gaf_setup(runner, go_json):
    for dataset, group in datasets_to_test:
        print(f"Testing {dataset} from {group}")
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
            '--only-dataset', dataset,
            '--gpad-gpi-output-version', '2.0',
            group
        ])

        print(f"Exit Code: {result.exit_code}")
        print(f"Standard Output: {result.stdout}")

        test_path = Path(__file__).parent / "groups" / group / f"{dataset}.gaf.gz"

        # Try finding the file in the root directory (for Makefile execution)
        root_path = Path(__file__).parent.parent / "groups" / group / f"{dataset}.gaf.gz"
        # Check which path exists and return the correct one
        if test_path.exists():
            zipped_gaf = test_path
            base_gaf_path = Path(__file__).parent / "groups" / group
        elif root_path.exists():
            zipped_gaf = root_path
            base_gaf_path = Path(__file__).parent.parent / "groups" / group
        else:
            raise FileNotFoundError(f"Could not find {dataset}.gaf.gz in either {test_path} or {root_path}")

        assert os.path.exists(zipped_gaf)

        assert os.path.exists(base_path)

        print("zipped gaf path", zipped_gaf)
        assert os.path.exists(zipped_gaf)

        unzipped_gaf = base_gaf_path / f"{dataset}.gaf"

        assert os.path.exists(unzipped_gaf)

        ontology = "go"
        ontology_graph = OntologyFactory().create(ontology, ignore_cache=True)

        gaf_parser = GafParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))

        # Open the GAF file and pass the file object to the parser
        with unzipped_gaf.open('r') as gaf_file:
            results = gaf_parser.parse(gaf_file)

        assert len(results) > 0
        print(metadata)

        base_config_path = Path(__file__).parent / "resources"

        metadata = base_config_path / "metadata"
        datasets = metadata / "datasets"
        assert os.path.exists(datasets)
        assert os.path.exists(metadata)

        gpad_parser = GpadParser(config=assocparser.AssocParserConfig(ontology=ontology_graph))

        unzipped_gaf = base_gaf_path / f"{dataset}.gaf"
        gpad_path = base_gaf_path / f"{dataset}.gpad"

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
