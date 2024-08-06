import pytest
from click.testing import CliRunner
from bin.validate import produce
import os

@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.skipif(
    not os.path.exists('/Users/SMoxon/Documents/src/go-site/metadata') and not os.path.exists('go-basic.json'),
    reason="Required files go-site/metadata and go-basic.json do not exist",
)
def test_produce_with_required_options(runner):
    result = runner.invoke(produce, [
        '-m', '/Users/SMoxon/Documents/src/go-site/metadata',
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









