import pytest
from click.testing import CliRunner
from bin.validate import produce
import os, requests


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def metadata(scope='session'):
    # GitHub repository details
    repo_owner = 'geneontology'
    repo_name = 'go-site'
    directory_path = 'metadata'
    base_url = f'https://api.github.com/repos/{repo_owner}/{repo_name}/contents/{directory_path}'

    # Local directory to save the files
    local_directory = os.path.join(os.getcwd(), 'metadata')

    # Create the local directory if it doesn't exist
    if not os.path.exists(local_directory):
        os.makedirs(local_directory)

    # Get the list of files in the directory
    response = requests.get(base_url)
    if response.status_code == 200:
        files = response.json()
        for file in files:
            if file['type'] == 'file':
                file_url = file['download_url']
                file_name = file['name']
                file_path = os.path.join(local_directory, file_name)

                # Download and save the file
                file_response = requests.get(file_url)
                if file_response.status_code == 200:
                    with open(file_path, 'wb') as f:
                        f.write(file_response.content)
                    print(f'Downloaded: {file_name}')
                else:
                    print(f'Failed to download: {file_name}')
    else:
        print(f'Failed to retrieve directory contents. Status code: {response.status_code}')
    return local_directory


@pytest.fixture(scope='session')
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


@pytest.mark.skipif(
    not os.path.exists('metadata') and not os.path.exists('go-basic.json'),
    reason="Required files go-site/metadata and go-basic.json do not exist",
)
def test_produce_with_required_options(runner, metadata, go_json):
    result = runner.invoke(produce, [
        '-m', 'metadata',
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








