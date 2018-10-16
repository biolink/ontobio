from ontobio.sim.owlsim2_engine import OwlSim2Engine
from ontobio.model.similarity import IcStatistic


class TestOwlSimIntegration():
    """
    Integration tests for ontobio and owlsim2
    """

    @classmethod
    def setup_class(self):
        self.owlsim2 = OwlSim2Engine()

    @classmethod
    def teardown_class(self):
        self.owlsim2 = None

    def test_stat_type(self):
        """
        Test stat type
        """
        assert isinstance(self.owlsim2.statistics, IcStatistic)

    def test_fetch_stats(self):
        """
        Test that we're getting stats back and they're the
        correct type
        """
        assert isinstance(self.owlsim2.statistics.mean_mean_ic, float)
        assert isinstance(self.owlsim2.statistics.individual_count, int)

    def test_fetch_ic(self):
        """
        Fetch two classes that are parent-child
        and test that the child has a higher IC
        than the parent
        :return:
        """
        classes = ['HP:0000739', 'HP:0000740']
        ic_dict = self.owlsim2.get_profile_ic(classes)
        assert isinstance(ic_dict['HP:0000740'], float)
        assert ic_dict['HP:0000740'] > ic_dict['HP:0000739']

    def test_get_annotation_suff(self):
        classes = ['HP:0000739', 'HP:0000740']
        negated_classes = []
        annot_suff = self.owlsim2.get_annotation_sufficiency(classes, negated_classes)
        assert 0 < annot_suff.simple_score < 1
        assert 0 < annot_suff.scaled_score < 1
        assert 0 < annot_suff.categorical_score < 1
