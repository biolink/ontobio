from enum import Enum


class HomologyTypes(Enum):
    """
    Core homology relations from RO
    """
    Ortholog = 'RO:HOM0000017'
    LeastDivergedOrtholog = 'RO:HOM0000020'
    Homolog = 'RO:HOM0000007'
    Paralog = 'RO:HOM0000011'
    InParalog = 'RO:HOM0000023'
    OutParalog = 'RO:HOM0000024'
    Ohnolog = 'RO:HOM0000022'
    Xenolog = 'RO:HOM0000018'

class Evidence():
    axiom_has_evidence = 'RO:0002612'
    evidence_with_support_from =  'RO:0002614'
    has_supporting_reference =  'SEPIO:0000124'
    information_artefact = 'IAO:0000311'

    _prefixmap = {
        'SEPIO': 'http://purl.obolibrary.org/obo/SEPIO_',
        'IAO': 'http://purl.obolibrary.org/obo/IAO_',
        'RO': 'http://purl.obolibrary.org/obo/RO_',
    }
    
class OboRO():
    part_of = 'BFO:0000050'
    occurs_in = 'BFO:0000066'
    enabled_by = 'RO:0002333'
    enables = 'RO:0002327'
    involved_in = 'RO:0002331'
    in_taxon = 'RO:0002162'
    colocalizes_with = 'RO:0002325'

def map_legacy_pred(pred):
    if '#' in pred:
        lbl = pred.split('#')[-1]
        if lbl == 'part_of':
            return 'BFO:0000050'
        if '_part_of' in lbl:
            # for FMA
            return 'BFO:0000050'
    return pred
    
