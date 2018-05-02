from typing import Dict, List, Optional, NamedTuple

Highlight = NamedTuple(
    'Highlight', [
        ('highlight', str),
        ('match', str),
        ('has_highlight', bool)
    ]
)


class SearchResults:
    """
    Search results class from transformed solr results

    docs: pysolr.Results.docs, docs returned by solr (schema dependent)

    numFound: count of total docs for query,
              {HTTPResponse.json()}.response.numFound or pysolr.Results.docs

    facet_count:
        A solr facet field looks like this: [field1, count1, field2, count2, ..., fieldN, countN]

          We translate this to a dict {f1: c1, ..., fn: cn}

    highlighting: dictionary of highlights per id:
        ex: {id1: "<em> some highlight </em> some not highlighted"}

    """

    def __init__(self,
                 docs: List[Dict],
                 numFound: int,
                 facet_counts: Dict,
                 highlighting: Optional[Dict[str, str]]):
        self.docs = docs
        self.numFound = numFound
        self.facet_counts = facet_counts
        self.highlighting = highlighting
        return


class AutocompleteResult:
    """
    Data class for single autocomplete result

    id: curie formatted id
    label: primary label (rdfs:label)
    match: matched part of document (may be primary label, synonym, id, etc)
    category: Neo4J label(s)
    taxon: taxon as NCBITaxon curie
    taxon_label: taxon label
    highlight: solr highlight
    has_highlight: True if highlight can be interpreted as html, else False
    """
    def __init__(self,
                 id: str,
                 label: str,
                 match: str,
                 category: List[str],
                 taxon: str,
                 taxon_label: str,
                 highlight: str,
                 has_highlight: bool):
        self.id = id
        self.label = label
        self.match = match
        self.category = category
        self.taxon = taxon
        self.taxon_label = taxon_label
        self.highlight = highlight
        self.has_highlight = has_highlight
        return
