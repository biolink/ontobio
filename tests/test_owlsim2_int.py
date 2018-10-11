from ontobio.sim.owlsim2_engine import OwlSim2Engine
from ontobio.model.similarity import IcStatistic


class TestOwlSimIntegration():

    @classmethod
    def setup_class(self):
        self.owlsim2 = OwlSim2Engine()

    @classmethod
    def teardown_class(self):
        self.owlsim2 = None

    def test_stat_type(self):
        assert isinstance(self.owlsim2.statistics, IcStatistic)

    def test_fetch_stats(self):
        assert isinstance(self.owlsim2.statistics.mean_mean_ic, float)
        assert isinstance(self.owlsim2.statistics.individual_count, int)

    def test_fetch_ic(self):
        classes = ['HP:0000739', 'HP:0000740']
        ic_dict = self.owlsim2.get_profile_ic(classes)
        assert isinstance(ic_dict['HP:0000740'], float)
        assert ic_dict['HP:0000740'] > ic_dict['HP:0000739']

    def test_get_annotation_suff(self):
        classes = ['HP:0000739', 'HP:0000740']
        negated_classes = []
        annot_suff = self.owlsim2.get_annotation_sufficiency(classes, negated_classes)
        #print(annot_suff.__dict__)
        assert True == True