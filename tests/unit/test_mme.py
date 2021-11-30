from pathlib import Path
import json

import pytest
from dacite import from_dict, Config

from ontobio.sim.mme import clean_feature_ids, query_owlsim
from ontobio.model.mme.request import MmeRequest, Observed
from ontobio.sim.api.owlsim2 import OwlSim2Api
from ontobio.sim.phenosim_engine import PhenoSimEngine


patient_1 = Path(__file__).parent / 'resources' / 'mme' / 'patient1.json'
owlsim_api = PhenoSimEngine(OwlSim2Api())


@pytest.mark.parametrize(
    "id, clean_id",
    [
        ("MIM:1234", "OMIM:1234"),
        ("SHH", "HGNC:10848"),
        ("some-term-we-dont-have", "some-term-we-dont-have")
    ]
)
def test_clean_feature_ids(id, clean_id):
    test_id = clean_feature_ids(id)
    assert clean_id == test_id


def test_mme_query():
    with open(patient_1, 'r') as patient_1_json:
        patient1 = json.load(patient_1_json)
    mme_request = from_dict(MmeRequest, patient1, config=Config(cast=[Observed]))
    response = query_owlsim(mme_request, owlsim_api, taxon='9606')
    assert response.results[0].score.patient >= 0
    assert response.results[0]._disease.startswith('MONDO')
