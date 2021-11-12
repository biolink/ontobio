from ontobio.model.biomodel import BioObject
from dacite import from_dict


def test_optional_values_validate():
    """
    Tests that optional values properly validate with dacite
    """
    test_object = {
        'id': 'PMID:1234',
        'lbl': None
    }
    bioobject = from_dict(BioObject, test_object)
    assert bioobject.id == 'PMID:1234'
    assert bioobject.lbl is None
