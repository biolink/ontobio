from ontobio.ontol_factory import OntologyFactory
import logging

def test_alt_id():
    """
    test alt_ids and replaced by
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/alt_id_test.json')

    for x in ont.nodes():
        if ont.is_obsolete(x):
            if ont.replaced_by(x):
                print('{} --> {}'.format(x, ont.replaced_by(x)))
            else:
                print('OBS: {} no replacement'.format(x))
                      
