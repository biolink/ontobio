from enum import Enum


class PairwiseDist(Enum):
    EUCLIDEAN   = 'euclidean'
    JIN_CONRATH = 'jin_conrath'


class PairwiseSim(Enum):
    GEOMETRIC = 'geometric'  # geometric mean of ic and jaccard (phenodigm)
    IC        = 'ic'
    JACCARD   = 'jaccard'


class MatrixMetric(Enum):
    MAX = 'max'  # Max
    AVG = 'avg'  # Average
    BMA = 'bma'  # Best Match Average


class SimAlgorithm(Enum):
    JACCARD = 'jaccard'
    PHENODIGM = 'phenodigm'
    RESNIK = 'resnik'
    SYMMETRIC_RESNIK = 'symmetric_resnik'
    SIM_GIC = 'simGIC'
    COSINE = 'cosine'
    NAIVE_BAYES_TWO_STATE = 'naive-bayes-fixed-weight-two-state'
    NAIVE_BAYES_TWO_STATE_NO_BLANKET = 'naive-bayes-fixed-weight-two-state-NOBLANKET'
    MAX_INFORMATION = 'max-information'
    BAYES_NETWORK = 'bayesian-network'
    GRID = 'grid'
    NAIVE_BAYES_THREE_STATE = 'naive-bayes-fixed-weight-three-state'
    BAYES_VARIABLE = 'bayes-variable'
    GRID_NEGATED = 'grid-negated'