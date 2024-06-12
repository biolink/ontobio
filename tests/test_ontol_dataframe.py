from ontobio.ontol_factory import OntologyFactory
import ontobio.ontol_dataframe as ofr
import logging


def test_ldef():
    """
    Load ontology from JSON
    """
    factory = OntologyFactory()
    print("Creating ont")
    ont = factory.create('tests/resources/pato.json')

    df = ofr.make_ontology_dataframe([ont])
    print(df)
