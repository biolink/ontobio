import pytest
from click.testing import CliRunner
from bin.validate import produce
import os
import requests
import shutil


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


def test_produce_with_required_options(runner, go_json):
    # Ensure that the required files are created
    metadata = os.getcwd() + '/resources/metadata/datasets'
    assert os.path.exists(metadata), f"Metadata directory does not exist: {metadata}"
    assert os.path.exists(go_json), f"go-basic.json file does not exist: {go_json}"

    result = runner.invoke(produce, [
        '-m', 'resources/metadata',
        '--gpad',
        '-t', '.',
        '-o', 'go-basic.json',
        '--base-download-url', 'http://skyhook.berkeleybop.org/snapshot/',
        '--only-dataset', 'goa_chicken',
        'goa',
        '--gpad-gpi-output-version', '2.0'
    ])
    print(result.exit_code)
    print(result.stdout)
    # assert result.exit_code == 0
    # assert "Making products" in result.output
    # assert "Products will go in" in result.output
    # assert "Loading ontology" in result.output
    print(metadata)

    # Remove the "go-basic.json" file
    json_file = "go-basic.json"
    if os.path.exists(json_file):
        os.remove(json_file)
