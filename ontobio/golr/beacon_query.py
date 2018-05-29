from ontobio.golr.golr_query import GolrAssociationQuery, M

class BeaconAssociationQuery(GolrAssociationQuery):
    """
    A query object for performing the beacon association search functionality.
    Note that such searches are directionless: sources and targets have a
    different meaning from subjects and objects.

    Fields
    ------
    sources : List[str]
        A list of identifiers to match either the subject or object of an
        association.
    targets : List[str]
        A list of identifiers to filter the relata not matched by sources
    keywords : List[str]
        A list of terms to filter the labels of the relata not matched by
        sources
    categories : List[str]
        A list of categories to filter the category of the relata not matched
        by sources
    relations : List[str]
        A list of relationship labels to filter the associations on
    """
    def __init__(
        self,
        sources,
        targets=None,
        keywords=None,
        categories=None,
        relations=None,
        rows=10,
        start=None
    ):
        super().__init__(
            select_fields=_get_select_fields(),
            rows=rows,
            start=start
        )

        self.sources = sources
        self.targets = targets
        self.keywords = keywords
        self.categories = categories
        self.relations = relations

        filters = {}

        if self.targets is not None and self.targets != []:
            filters['closure'] = _make_disjunction(self.targets, '"')

        if self.keywords is not None and self.keywords != []:
            filters['label'] = _make_disjunction(self.keywords, '*')

        if self.categories is not None and self.categories != []:
            filters['category'] = _make_disjunction(self.categories, '*')

        source_disjunction=_make_disjunction(self.sources, '"')
        self.q=_build_query(source_disjunction, filters)

        if self.relations is not None and relations != []:
            relation_disjunction = _make_disjunction(self.relations, '"')
            self.q += ' AND (relation_label: ' + relation_disjunction + ')'

def _build_query(sources, filters):
    q='((object_closure: ' + sources + ')'
    for key in filters.keys():
        q+=' AND (subject_' + key + ': ' + filters[key] + ')'

    q += ') OR ('
    q += '(subject_closure: ' + sources + ')'
    for key in filters.keys():
        q+=' AND (object_' + key + ': ' + filters[key] + ')'
    q += ')'
    return q

def _make_disjunction(items, wrapping=''):
    return '(' + ' OR '.join(wrapping + i + wrapping for i in items) + ')'

def _get_select_fields():
    select_fields = [
        M.ID,
        M.SUBJECT,
        M.SUBJECT_LABEL,
        M.SUBJECT_CATEGORY,
        M.SUBJECT_TAXON,
        M.SUBJECT_TAXON_LABEL,
        M.RELATION,
        M.RELATION_LABEL,
        M.OBJECT,
        M.OBJECT_LABEL,
        M.OBJECT_TAXON,
        M.OBJECT_TAXON_LABEL,
        M.OBJECT_CATEGORY
    ]

    return select_fields
