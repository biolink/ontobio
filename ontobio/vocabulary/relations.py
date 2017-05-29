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
    
class OboRO():
    part_of = 'BFO:0000050'
    occurs_in = 'BFO:0000066'
    enabled_by = 'RO:0002333'
    in_taxon = 'RO:0002162'
