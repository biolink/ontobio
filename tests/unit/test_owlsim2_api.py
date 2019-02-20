from ontobio.sim.api.owlsim2 import OwlSim2Api
from ontobio.vocabulary.similarity import SimAlgorithm
from unittest.mock import patch


class TestOwlSim2Api():
    """
    Unit tests for owlsim2 api
    """

    @classmethod
    def setup_class(self):
        patch('ontobio.sim.api.owlsim2.get_owlsim_stats',  return_value=(None, None)).start()
        self.sim_api = OwlSim2Api()

    @classmethod
    def teardown_class(self):
        self.sim_api = None

    def test_rank_results(self):
        """
        Test OwlSim2Api._rank_results
        """
        test_method = SimAlgorithm.SIM_GIC
        test_results = [
            {'simGIC': 0.405}, {'simGIC': 0.511}, {'simGIC': 0.405}, {'simGIC': 0.908}
        ]
        expected_output = [
            {'simGIC': 0.908, 'rank': 1}, {'simGIC': 0.511, 'rank': 2},
            {'simGIC': 0.405, 'rank': 3}, {'simGIC': 0.405, 'rank': 3}
        ]
        assert self.sim_api._rank_results(test_results, test_method) == expected_output
