from ontobio.sim.annotation_scorer import AnnotationScorer
from ontobio.sim.api.owlsim2 import OwlSim2Api
from ontobio.model.similarity import IcStatistic
from unittest.mock import patch


class TestAnnotationSufficiency():
    """
    Unit tests for AnnotationScorer

    Mock data based on star trek example
    https://www.slideshare.net/mhaendel/patientled-deep-phenotyping-using-a-
    layfriendly-version-of-the-human-phenotype-ontology-90800501/5
    """

    @classmethod
    def setup_class(self):
        patch('ontobio.sim.api.owlsim2.get_owlsim_stats',  return_value=(None, None)).start()
        self.ic_store = OwlSim2Api()
        self.annot_scorer = AnnotationScorer(self.ic_store)

        self.ic_store.statistics = IcStatistic(
            mean_mean_ic = 6.82480,
            mean_sum_ic = 120.89767,
            mean_cls = 15.47425,
            max_max_ic = 16.16108,
            max_sum_ic = 6746.96160,
            individual_count = 65309,
            mean_max_ic = 9.51535
        )
        self.ic_store.category_statistics = {
            'ear feature': IcStatistic(
                mean_mean_ic=7.55126,
                mean_sum_ic=26.60304,
                mean_cls=3.40207,
                max_max_ic=16.15508,
                max_sum_ic=613.22168,
                individual_count=6004,
                mean_max_ic=8.48152,
                descendants=['pointy ears', 'large ears', 'small ears']
            ),
            'skin feature': IcStatistic(
                mean_mean_ic=7.55126,
                mean_sum_ic=26.60304,
                mean_cls=3.40207,
                max_max_ic=16.15508,
                max_sum_ic=613.22168,
                individual_count=6004,
                mean_max_ic=8.48152,
                descendants=['blue skin', 'orange skin', 'increased pigmentation']
            ),
        }
        self.mock_ic_values = {
            'pointy ears': 12.0021,
            'large ears': 8.2345,
            'small ears': 8.1536,
            'blue skin': 10.12593,
            'orange skin': 15.1592,
            'increased pigmentation': 5.5926
        }
        self.negation_weight = .23
        self.category_weight = .33

    @classmethod
    def teardown_class(self):
        self.annot_scorer = None
        self.ic_store = None

    def test_get_simple_score(self):
        """
        Test ontobio.sim.sim_engine.InformationContentStore._get_simple_score
        no negation
        """
        classes = ['blue skin', 'pointy ears']
        negated_classes = []

        simple_score = self.annot_scorer._get_simple_score(
            classes, negated_classes, self.ic_store.statistics.mean_mean_ic,
            self.ic_store.statistics.mean_max_ic, self.ic_store.statistics.mean_sum_ic,
            self.negation_weight, self.mock_ic_values
        )
        assert simple_score == 0.7276770236073753

    def test_get_simple_score_w_negation(self):
        """
        Test ontobio.sim.sim_engine.InformationContentStore._get_simple_score
        with negation
        """
        classes = ['blue skin', 'pointy ears']
        negated_classes = ['large ears', 'increased pigmentation']

        simple_score = self.annot_scorer._get_simple_score(
            classes, negated_classes, self.ic_store.statistics.mean_mean_ic,
            self.ic_store.statistics.mean_max_ic, self.ic_store.statistics.mean_sum_ic,
            self.negation_weight, self.mock_ic_values
        )
        assert simple_score == 0.7364454115065521

    def test_get_cat_score(self):
        """
        Test ontobio.sim.sim_engine.InformationContentStore._get_categorical_score
        no negation
        """
        classes = ['blue skin', 'pointy ears']
        negated_classes = []
        categories = ['ear feature', 'skin feature']

        categorical_score = self.annot_scorer._get_categorical_score(
            classes, negated_classes, categories,
            self.negation_weight, self.mock_ic_values
        )

        assert categorical_score == 0.7002519289078384

    def test_get_cat_score_w_negation(self):
        """
        Test ontobio.sim.sim_engine.InformationContentStore._get_categorical_score
        with negation
        """
        classes = ['blue skin', 'pointy ears']
        negated_classes = ['large ears', 'increased pigmentation']

        categories = ['ear feature', 'skin feature']

        categorical_score = self.annot_scorer._get_categorical_score(
            classes, negated_classes, categories,
            self.negation_weight, self.mock_ic_values
        )

        assert categorical_score == 0.7201759238096741

    def test_get_scaled_score(self):
        """
        Test ontobio.sim.sim_engine.InformationContentStore._get_scaled_score
        """
        simple_score = 0.73
        categorical_score = 0.82
        scaled_score = self.annot_scorer._get_scaled_score(
            simple_score, categorical_score, self.category_weight)

        assert scaled_score == 0.75233082706766907
