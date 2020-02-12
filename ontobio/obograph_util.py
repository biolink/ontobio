"""
Mapping between obograph-JSON format and networkx
"""

from ontobio.ontol import LogicalDefinition, PropertyChainAxiom
from ontobio.vocabulary.relations import map_legacy_pred
from ontobio.util.scigraph_util import get_curie_map
from ontobio.golr.golr_associations import search_associations

import json
import networkx
import logging
from prefixcommons.curie_util import expand_uri, contract_uri
from diskcache import Cache
import tempfile


cache = Cache(tempfile.gettempdir())


logger = logging.getLogger(__name__)


class OboJsonMapper(object):
    def __init__(self,
                 digraph=None,
                 context=None):
        self.digraph = digraph
        self.context = context if context is not None else {}

    def add_obograph_digraph(
            self,
            og,
            node_type=None,
            predicates=None,
            xref_graph=None,
            logical_definitions=None,
            property_chain_axioms=None,
            parse_meta=True,
            reverse_edges=True,
            **args):
        """
        Converts a single obograph to Digraph edges and adds to an existing networkx DiGraph
        """
        digraph = self.digraph
        logger.info("NODES: {}".format(len(og['nodes'])))

        # if client passes an xref_graph we must parse metadata
        if xref_graph is not None:
            parse_meta = True

        for node in og['nodes']:
            is_obsolete = 'is_obsolete' in node and node['is_obsolete'] == 'true'
            if is_obsolete:
                continue
            if node_type is not None and ('type' not in node or node['type'] != node_type):
                continue
            id = self.contract_uri(node['id'])
            digraph.add_node(id, **node)
            if 'lbl' in node:
                digraph.node[id]['label'] = node['lbl']
            if parse_meta and 'meta' in node:
                if node['meta'] is None:
                    node['meta'] = {}
                meta = self.transform_meta(node['meta'])
                if xref_graph is not None and 'xrefs' in meta:
                    for x in meta['xrefs']:
                        xref_graph.add_edge(self.contract_uri(x['val']), id, source=id)
        logger.info("EDGES: {}".format(len(og['edges'])))
        for edge in og['edges']:
            sub = self.contract_uri(edge['sub'])
            obj = self.contract_uri(edge['obj'])
            pred = self.contract_uri(edge['pred'])
            pred = map_legacy_pred(pred)
            if pred == 'is_a':
                pred = 'subClassOf'
            if predicates is None or pred in predicates:
                meta = edge['meta'] if 'meta' in edge else {}
                if reverse_edges:
                    digraph.add_edge(obj, sub, pred=pred, **meta)
                else:
                    digraph.add_edge(sub, obj, pred=pred, **meta)

        if 'equivalentNodesSets' in og:
            nslist = og['equivalentNodesSets']
            logger.info("CLIQUES: {}".format(len(nslist)))
            for ns in nslist:
                equivNodeIds = ns['nodeIds']
                for i in ns['nodeIds']:
                    ix = self.contract_uri(i)
                    for j in ns['nodeIds']:
                        if i != j:
                            jx = self.contract_uri(j)
                            digraph.add_edge(ix, jx, pred='equivalentTo')
        if logical_definitions is not None and 'logicalDefinitionAxioms' in og:
            for a in og['logicalDefinitionAxioms']:
                ld = LogicalDefinition(self.contract_uri(a['definedClassId']),
                                       [self.contract_uri(x) for x in a['genusIds']],
                                       [(self.contract_uri(x['propertyId']),
                                         self.contract_uri(x['fillerId'])) for x in a['restrictions'] if x is not None])
                logical_definitions.append(ld)
        if property_chain_axioms is not None and 'propertyChainAxioms' in og:
            for a in og['propertyChainAxioms']:
                pca = PropertyChainAxiom(predicate_id=self.contract_uri(a['predicateId']),
                                         chain_predicate_ids=[self.contract_uri(x) for x in a['chainPredicateIds']])
                property_chain_axioms.append(pca)

    def transform_meta(self, meta):
        if 'basicPropertyValues' in meta:
            for x in meta['basicPropertyValues']:
                x['pred'] = self.contract_uri(x['pred'])
                x['val'] = self.contract_uri(x['val'])
        return meta

    def contract_uri(self, uri):
        if len(self.context.keys()) > 0:
            curies = contract_uri(uri, cmaps=[self.context])
            if len(curies) > 0:
                return sorted(curies, key=len)[0] # sort by length

        curies = sorted(contract_uri(uri), key=len) # Sort by length
        if len(curies) > 0:
            return curies[0]
        else:
            return uri


def convert_json_file(obographfile, **args):
    """
    Return a networkx MultiDiGraph of the ontologies
    serialized as a json string

    """
    file = open(obographfile, 'r')
    jsonstr = file.read()
    file.close()
    return convert_json_object(json.loads(jsonstr), **args)


def convert_json_object(obographdoc, reverse_edges=True, **args):
    """
    Return a networkx MultiDiGraph of the ontologies
    serialized as a json object

    """
    digraph = networkx.MultiDiGraph()
    xref_graph = networkx.MultiGraph()
    logical_definitions = []
    property_chain_axioms = []
    context = obographdoc.get('@context',{})
    logger.info("CONTEXT: {}".format(context))
    mapper = OboJsonMapper(digraph=digraph, context=context)
    ogs = obographdoc['graphs']
    base_og = ogs[0]
    for og in ogs:
        # TODO: refactor this
        mapper.add_obograph_digraph(og, xref_graph=xref_graph,
                                    logical_definitions=logical_definitions,
                                    property_chain_axioms=property_chain_axioms,
                                    reverse_edges=reverse_edges,
                                    **args)

    return {
        'id': base_og.get('id'),
        'meta': base_og.get('meta'),
        'graph': mapper.digraph,
        'xref_graph': xref_graph,
        'graphdoc': obographdoc,
        'logical_definitions': logical_definitions,
        'property_chain_axioms': property_chain_axioms
        }


def _get_association_nodes(digraph, sub, predicate, obj):
    """
    Given a subject, predicate, object, retrieve the OBAN association
    node from the evidence graph
    """
    subject_assocs = set()
    object_assocs = set()
    predicate_assocs = set()
    union_assoc = set()

    # A fast way of checking if the triple is reified is seeing if the
    # predicate exists as a node
    if predicate['pred'] in digraph.node:
        # association_has_subject
        for neighbor, edges in digraph.pred[sub].items():
            for edge in edges.values():
                if edge['pred'] == 'OBAN:association_has_subject':
                    subject_assocs.add(neighbor)

        # association_has_object
        for neighbor, edges in digraph.pred[obj].items():
            for edge in edges.values():
                if edge['pred'] == 'OBAN:association_has_object':
                    object_assocs.add(neighbor)

        # association_has_predicate
        for neighbor, edges in digraph.pred[predicate['pred']].items():
            for edge in edges.values():
                if edge['pred'] == 'OBAN:association_has_predicate':
                    predicate_assocs.add(neighbor)

        union_assoc = subject_assocs & object_assocs & predicate_assocs

    return union_assoc


def _triple_to_association(digraph, subject, predicate, obj):
    """
    Convert triple to association object
    """
    object_eq = []
    subject_eq = []
    if 'equivalentOriginalNodeTarget' in predicate:
        for eq in predicate['equivalentOriginalNodeTarget']:
            curies = contract_uri(eq, [get_curie_map()], shortest=True)
            if len(curies) != 0:
                object_eq.append(curies[0])

    if 'equivalentOriginalNodeSource' in predicate:
        for eq in predicate['equivalentOriginalNodeSource']:
            curies = contract_uri(eq, [get_curie_map()], shortest=True)
            if len(curies) != 0:
                subject_eq.append(curies[0])

    relation_lbl = predicate['lbl'][0] if predicate['lbl'] else None

    association = {
        'subject': {
            'id': subject,
            'label': digraph.node[subject]['lbl'],
            'iri': expand_uri(subject, [get_curie_map()])
        },
        'subject_eq': subject_eq,
        'relation': {
            'id': predicate['pred'],
            'label': relation_lbl,
            'iri': expand_uri(predicate['pred'], [get_curie_map()])
        },
        'object': {
            'id': obj,
            'label': digraph.node[obj]['lbl'],
            'iri': expand_uri(obj, [get_curie_map()])
        },
        'object_eq': object_eq,
        'provided_by': predicate['isDefinedBy'],
        'evidence_types': [],
        'publications': []
    }

    # get association node linked to ECO codes and publications
    association_nodes = _get_association_nodes(digraph, subject, predicate, obj)

    if len(list(association_nodes)) > 1:
        # This can happen with clique merging, for now log it
        # and combine both in association results
        logging.debug("Ambiguous association for %s, %s, %s",
                      subject, predicate, obj)

    for association_node in list(association_nodes):
        for obj, edges in digraph.adj[association_node].items():
            eco_codes = [eco['id'] for eco in association['evidence_types']]
            pubs = [pub['id'] for pub in association['publications']]

            for edge in edges.values():
                if edge['pred'] == 'RO:0002558' and obj not in eco_codes:
                    association['evidence_types'].append({
                        'id': obj,
                        'label': digraph.node[obj]['lbl']
                    })
                elif edge['pred'] == 'dc:source' and obj not in pubs:
                    association['publications'].append({
                        'id': obj,
                        'label': digraph.node[obj]['lbl']
                    })

    return association


def obograph_to_assoc_results(digraph, assoc_type, is_publication=False):
    """
    Converts a multidigraph from convert_json_object
    to a list of association objects, which is easier
    to parse downstream for graph and table views

    :param: digraph: networkx.multidigraph or digraph
    :return: List, list of golr association objects

    """
    # Filter out oban edges initially, then retrieve using
    # _triple_to_association
    filter_edges = [
        'OBAN:association_has_subject',
        'OBAN:association_has_object',
        'OBAN:association_has_predicate',
        'RO:0002558'  # ECO codes, etc
    ]
    if not assoc_type.startswith('publication'):
        # publications, web pages, etc
        filter_edges.append('dc:source')

    # Filter out has_affected_feature since there can be many variant
    # to disease and the variant to gene assoc is usually obvious
    if assoc_type == 'gene_disease':
        filter_edges.append('GENO:0000418')

    association_results = []

    # Neighbors is a dict of adjacent nodes and outgoing edges
    for sub, neighbors in digraph.adjacency():
        # Iterate over nodes connected to outgoing edges (objects)
        for obj, edges_dict in neighbors.items():
            # Iterate over all edges connecting subject and object
            for edge_attr in edges_dict.values():
                if edge_attr['pred'] in filter_edges:
                    continue
                association_results.append(_triple_to_association(
                    digraph, sub, edge_attr, obj))

    return association_results


@cache.memoize()
def get_evidence_tables(id, is_publication, user_agent):

    results = search_associations(
            fq={'id': id},
            facet=False,
            select_fields=['evidence_graph', 'association_type'],
            user_agent=user_agent)
    assoc_results = {}
    assoc = results['associations'][0] if len(results['associations']) > 0 else {}
    if assoc:
        eg = {'graphs': [assoc.get('evidence_graph')]}
        assoc_type = assoc['type']
        digraph = convert_json_object(eg, reverse_edges=False)['graph']
        assoc_results = obograph_to_assoc_results(digraph, assoc_type, is_publication)
        assoc_results = {
            'associations': assoc_results,
            'numFound': len(assoc_results)
        }
    return assoc_results
