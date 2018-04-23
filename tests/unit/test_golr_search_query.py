from ontobio.golr.golr_query import GolrSearchQuery, GolrLayPersonSearch
import json
import os
import pysolr
import pytest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock


class TestGolrSearchQuery():

    @classmethod
    def setup_class(self):
        self.manager = GolrSearchQuery()

        # Mock the PySolr search function to
        # return our test docs
        input_fh = os.path.join(os.path.dirname(__file__),
                                'resources/solr/solr-docs.json')
        input_docs = json.load(open(input_fh))
        self.test_results = pysolr.Results(input_docs)
        self.manager.solr.search = MagicMock(return_value=self.test_results)

    @classmethod
    def teardown_class(self):
        self.manager = None

    def test_longest_hl(self):
        test_data = [
            "<em>Muscle</em> <em>atrophy</em>, generalized",
            "Generalized <em>muscle</em> degeneration",
            "Diffuse skeletal <em>muscle</em> wasting"
        ]
        expected = "<em>Muscle</em> <em>atrophy</em>, generalized"
        results = self.manager._get_longest_hl(test_data)
        assert expected == results

    def test_longest_hl_ambiguous(self):
        test_data = [
            "<em>Muscle</em> <em>atrophy</em>, generalized",
            "Generalized <em>muscle</em> degeneration",
            "Diffuse skeletal <em>muscle</em> wasting",
            "<em>Muscle</em> <em>atrophy</em>, not generalized",
        ]
        expected = "<em>Muscle</em> <em>atrophy</em>, generalized"
        results = self.manager._get_longest_hl(test_data)
        assert expected == results

    def test_hl_to_string(self):
        test_data = "Foo <em>Muscle</em> bar <em>atrophy</em>, generalized"
        expected = "Foo Muscle bar atrophy, generalized"
        results = self.manager._hl_as_string(test_data)
        assert expected == results

    def test_invalid_xml(self):
        test_data = "Foo<Foo> <em>Muscle</em> bar <em>atrophy</em>, generalized"
        pytest.raises(ET.ParseError, self.manager._hl_as_string, test_data)

    def test_autocomplete_doc_conversion(self):
        """
        Given a sample solr output as a pysolr.Results object
        test that _process_autocomplete_results returns the
        expected object
        """
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/solr/autocomplete-expected.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager._process_autocomplete_results(self.test_results)

        assert json.dumps(processed_docs, sort_keys=True) == \
               json.dumps(output_docs,
                          default=lambda obj: getattr(obj, '__dict__', str(obj)),
                          sort_keys=True)

    def test_search_doc_conversion(self):
        """
        Given a sample solr output as a pysolr.Results object
        test that _process_autocomplete_results returns the
        expected object
        """
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/solr/search-expected.json')
        processed_docs = json.load(open(expected_fh))

        output_docs = self.manager._process_search_results(self.test_results)

        assert json.dumps(processed_docs, sort_keys=True) == \
               json.dumps(output_docs,
                          default=lambda obj: getattr(obj, '__dict__', str(obj)),
                          sort_keys=True)

    def test_search(self):
        """
        Given a mock PySolr.search method test that
        search() returns the expected object
        """
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/solr/search-expected.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager.search()

        assert json.dumps(processed_docs, sort_keys=True) == \
               json.dumps(output_docs,
                          default=lambda obj: getattr(obj, '__dict__', str(obj)),
                          sort_keys=True)

    def test_autocomplete(self):
        """
        Given a mock PySolr.search method test that
        autocomplete() returns the expected object
        """
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/solr/autocomplete-expected.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager.autocomplete()

        assert json.dumps(processed_docs, sort_keys=True) == \
               json.dumps(output_docs,
                          default=lambda obj: getattr(obj, '__dict__', str(obj)),
                          sort_keys=True)


class TestGolrLayPersonSearch():

    @classmethod
    def setup_class(self):
        self.manager = GolrLayPersonSearch()

        # Mock the PySolr search function to
        # return our test docs
        input_fh = os.path.join(os.path.dirname(__file__),
                                'resources/solr/layperson-docs.json')
        input_docs = json.load(open(input_fh))
        self.test_results = pysolr.Results(input_docs)
        self.manager.solr.search = MagicMock(return_value=self.test_results)

    @classmethod
    def teardown_class(self):
        self.manager = None

    def test_lay_doc_conversion(self):
        """
        Given a sample solr output as a pysolr.Results object
        test that _process_layperson_results returns the
        expected object
        """
        expected_fh = os.path.join(os.path.dirname(__file__),
                                  'resources/solr/layperson-expected.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager._process_layperson_results(self.test_results)

        assert json.dumps(processed_docs, sort_keys=True) == json.dumps(output_docs, sort_keys=True)

    def test_autocomplete(self):
        """
        Given a mock PySolr.search method test that
        autocomplete() returns the expected object
        """
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/solr/layperson-expected.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager.autocomplete()

        assert json.dumps(processed_docs, sort_keys=True) == json.dumps(output_docs, sort_keys=True)
