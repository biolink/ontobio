"""
Test in-memory semsearch
"""
from ontobio.io.gafparser import GafParser
from ontobio.assoc_factory import AssociationSetFactory
from ontobio.ontol_factory import OntologyFactory
from ontobio.sim.api.semsearch import SemSearchEngine
import logging

POMBASE = "tests/resources/truncated-pombase.gaf"
ONT = "tests/resources/go-truncated-pombase.json"
#GENES = ['clp1', 'dhc1', 'dli1', 'cdc2', 'mcm4', 'ark1', 'ptc1', 'cdc13', 'cdc15']
#GENES = ['clp1', 'mcm4', 'cdc2', 'ark1', 'ptc1', 'cdc13']
GENES = ['clp1', 'cdc2', 'cdc13']

#logging.basicConfig(level=logging.DEBUG)

def test_semsearch():
    afa = AssociationSetFactory()
    f = POMBASE
    ont = OntologyFactory().create(ONT)
    parser = GafParser()
    assocs = parser.parse(POMBASE, skipheader=True)
    assocs = [a for a in assocs if a['subject']['label'] in GENES]
    aset = afa.create_from_assocs(assocs,
                                  ontology=ont)
    ont = aset.subontology()
    aset.ontology = ont
    logging.info('Genes={} Terms={}'.format(len(aset.subjects), len(ont.nodes())))

    print('STATS={}'.format(aset.as_dataframe().describe()))
    
    #genes = aset.subjects[0:5]
    sse = SemSearchEngine(assocmodel=aset)

    logging.info('Calculating all MICAs')
    sse.calculate_all_micas()

    #h5path = 'tests/resources/mica_ic.h5'
    #logging.info('Saving to {}'.format(h5path))
    #sse.mica_ic_df.to_hdf(h5path, key='mica_ic', mode='w')
    #logging.info('Saved to {}'.format(h5path))
    
    logging.info('Doing pairwise')
    for i in aset.subjects:
        for j in aset.subjects:
            sim = sse.pw_score_cosine(i,j)
            #print('{} x {} = {}'.format(i,j,sim))
            if i==j:
                assert(sim > 0.9999)
            tups = sse.pw_score_resnik_bestmatches(i,j)
            print('{} x {} = {} // {}'.format(i,j,sim, tups))
    
