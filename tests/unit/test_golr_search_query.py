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
        self.manager = GolrSearchQuery(taxon_map=False)

        # Mock the PySolr search function to
        # return our test docs
        input_fh = os.path.join(os.path.dirname(__file__),
                                'resources/solr/input/solr-docs.json')
        input_docs = json.load(open(input_fh))
        self.pysolr_results = pysolr.Results(input_docs)
        self.manager.solr.search = MagicMock(return_value=self.pysolr_results)

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
        expected_fh = os.path.join(
            os.path.dirname(__file__),
            'resources/solr/expected/autocomplete.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager._process_autocomplete_results(self.pysolr_results)

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
                                   'resources/solr/expected/search.json')
        processed_docs = json.load(open(expected_fh))

        output_docs = self.manager._process_search_results(self.pysolr_results)

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
                                   'resources/solr/expected/search.json')
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
        expected_fh = os.path.join(
            os.path.dirname(__file__),
            'resources/solr/expected/autocomplete.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager.autocomplete()

        assert json.dumps(processed_docs, sort_keys=True) == \
               json.dumps(output_docs,
                          default=lambda obj: getattr(obj, '__dict__', str(obj)),
                          sort_keys=True)

    def test_autocomplete_no_category(self):
        """
        Test for document without a category
        """
        # Provide a new mock file
        input_fh = os.path.join(os.path.dirname(__file__),
                                'resources/solr/input/autocomplete-nocat.json')
        input_docs = json.load(open(input_fh))
        self.manager.solr.search = MagicMock(return_value=pysolr.Results(input_docs))

        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/solr/expected/autocomplete-nocat.json')
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
                                'resources/solr/input/layperson-docs.json')
        input_docs = json.load(open(input_fh))
        self.pysolr_results = pysolr.Results(input_docs)
        self.manager.solr.search = MagicMock(return_value=self.pysolr_results)

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
                                   'resources/solr/expected/layperson.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager._process_layperson_results(self.pysolr_results)

        assert json.dumps(processed_docs, sort_keys=True) == json.dumps(output_docs, sort_keys=True)

    def test_autocomplete(self):
        """
        Given a mock PySolr.search method test that
        autocomplete() returns the expected object
        """
        expected_fh = os.path.join(os.path.dirname(__file__),
                                   'resources/solr/expected/layperson.json')
        processed_docs = json.load(open(expected_fh))
        output_docs = self.manager.autocomplete()

        assert json.dumps(processed_docs, sort_keys=True) == json.dumps(output_docs, sort_keys=True)


class TestGolrSearchParams():

    @classmethod
    def setup_class(self):
        self.manager = GolrLayPersonSearch()

    @classmethod
    def teardown_class(self):
        self.manager = None

    def test_prefix_filters(self):
        """
        Test that prefix filters are converted
        properly to solr params
        """
        prefix_filter = [
            '-OMIA',
            '-Orphanet',
            'DO',
            'OMIM',
            'MONDO'
        ]
        expected = [
            '-prefix:("OMIA" OR "Orphanet")',
            'prefix:("DO" OR "OMIM" OR "MONDO")'
        ]
        self.manager.prefix = prefix_filter
        params = self.manager.solr_params()
        assert params['fq'] == expected

    def test_prefix_filters_include_eq(self):
        """
        Test that prefix filters are converted
        properly to solr params
        """
        prefix_filter = [
            '-OMIA',
            '-Orphanet',
            'DO',
            'OMIM',
            'MONDO'
        ]
        expected = [
            '(-prefix:"OMIA" OR -equivalent_curie:OMIA\:*)',
            '(-prefix:"Orphanet" OR -equivalent_curie:Orphanet\:*)',
            '((prefix:"DO" OR equivalent_curie:DO\:*) OR (prefix:"OMIM" OR '
            'equivalent_curie:OMIM\:*) OR (prefix:"MONDO" OR equivalent_curie:MONDO\:*))'
        ]
        self.manager.prefix = prefix_filter
        self.manager.include_eqs = True
        params = self.manager.solr_params()
        assert params['fq'] == expected
