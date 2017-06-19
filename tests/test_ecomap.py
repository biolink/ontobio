from ontobio.ecomap import EcoMap

def test_ecomap():
    m = EcoMap()
    assert m.coderef_to_ecoclass('IEA','GO_REF:0000002') == 'ECO:0000256'
    assert m.coderef_to_ecoclass('IEA') == 'ECO:0000501'
    assert m.coderef_to_ecoclass('IEA','FAKE:ID') == 'ECO:0000501'
    assert m.ecoclass_to_coderef('ECO:0000501') == ('IEA',None)
    assert m.ecoclass_to_coderef('ECO:0000256') == ('IEA','GO_REF:0000002')
