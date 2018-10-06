class SimResult:
    """
    Data class similarity result
    """
    def __init__(self):
        "some foo"
        return


class IcStatistic:
    """
    Data class for ic statistics

    mean_mean_ic: average of the average IC per individual
    mean_sum_ic: average sumIC per individual
    mean_cls: float, avg number of classes per individual
    max_max_ic: maximum IC of class annotated to an individual
    max_sum_ic: maximum sumIC
    individual_count: number of individuals
    mean_max_ic: average maxIC per individual
    """
    def __init__(self,
                 mean_mean_ic: float,
                 mean_sum_ic: float,
                 mean_cls: float,
                 max_max_ic: float,
                 max_sum_ic: float,
                 individual_count: int,
                 mean_max_ic: float):
        self.mean_mean_ic = mean_mean_ic
        self.mean_sum_ic = mean_sum_ic
        self.mean_cls = mean_cls
        self.max_max_ic = max_max_ic
        self.max_sum_ic = max_sum_ic
        self.individual_count = individual_count
        self.mean_max_ic = mean_max_ic
        return

class AnnotationSufficiency:
    """
    Data class for annotation sufficiency object
    """
    def __init__(self,
                 simple_score: float,
                 scaled_score: float,
                 categorical_score: float):
        self.simple_score = simple_score
        self.scaled_score = scaled_score
        self.categorical_score = categorical_score
        return
