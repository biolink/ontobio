from enum import Enum


class HomologyTypes(Enum):
    Ortholog = 'RO:HOM0000017'
    LeastDivergedOrtholog = 'RO:HOM0000020'
    Homolog = 'RO:HOM0000007'
    Paralog = 'RO:HOM0000011'
    InParalog = 'RO:HOM0000023'
    OutParalog = 'RO:HOM0000024'
    Ohnolog = 'RO:HOM0000022'
    Xenolog = 'RO:HOM0000018'