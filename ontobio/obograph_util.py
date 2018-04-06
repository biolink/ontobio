"""
Mapping between obograph-JSON format and networkx
"""

import itertools
import re
import json

import networkx
import logging
from prefixcommons.curie_util import contract_uri
from ontobio.ontol import LogicalDefinition
from ontobio.vocabulary.relations import map_legacy_pred

class OboJsonMapper(object):
    def __init__(self,
                 digraph=None,
                 context=None):
        self.digraph = digraph
        self.context = context if context is not None else {}

    def add_obograph_digraph(self, og, node_type=None, predicates=None, xref_graph=None, logical_definitions=None,
                             parse_meta=True,
                             **args):
        """
        Converts a single obograph to Digraph edges and adds to an existing networkx DiGraph
        """
        digraph = self.digraph
        logging.info("NODES: {}".format(len(og['nodes'])))

        # if client passes an xref_graph we must parse metadata
        if xref_graph is not None:
            parse_meta = True

        for n in og['nodes']:
            is_obsolete =  'is_obsolete' in n and n['is_obsolete'] == 'true'
            if is_obsolete:
                continue
            if node_type is not None and ('type' not in n or n['type'] != node_type):
                continue
            id = self.contract_uri(n['id'])
            digraph.add_node(id, attr_dict=n)
            if 'lbl' in n:
                digraph.node[id]['label'] = n['lbl']
            if parse_meta and 'meta' in n:
                if n['meta'] is None:
                    n['meta'] = {}
                meta = self.transform_meta(n['meta'])
                if xref_graph is not None and 'xrefs' in meta:
                    for x in meta['xrefs']:
                        xref_graph.add_edge(self.contract_uri(x['val']), id, source=id)
        logging.info("EDGES: {}".format(len(og['edges'])))
        for e in og['edges']:
            sub = self.contract_uri(e['sub'])
            obj = self.contract_uri(e['obj'])
            pred = self.contract_uri(e['pred'])
            pred = map_legacy_pred(pred)
            if pred == 'is_a':
                pred = 'subClassOf'
            if predicates is None or pred in predicates:
                digraph.add_edge(obj, sub, pred=pred)
        if 'equivalentNodesSets' in og:
            nslist = og['equivalentNodesSets']
            logging.info("CLIQUES: {}".format(len(nslist)))
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

    def transform_meta(self, m):
        if 'basicPropertyValues' in m:
            for x in m['basicPropertyValues']:
                x['pred'] = self.contract_uri(x['pred'])
                x['val'] = self.contract_uri(x['val'])
        return m

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
    f = open(obographfile, 'r')
    jsonstr = f.read()
    f.close()
    return convert_json_object(json.loads(jsonstr), **args)

def convert_json_object(obographdoc, **args):
    """
    Return a networkx MultiDiGraph of the ontologies
    serialized as a json object

    """
    digraph = networkx.MultiDiGraph()
    xref_graph = networkx.MultiGraph()
    logical_definitions = []
    context = obographdoc.get('@context',{})
    logging.info("CONTEXT: {}".format(context))
    mapper = OboJsonMapper(digraph=digraph, context=context)
    ogs = obographdoc['graphs']
    base_og = ogs[0]
    for og in ogs:
        # TODO: refactor this
        mapper.add_obograph_digraph(og, xref_graph=xref_graph,
                                    logical_definitions=logical_definitions, **args)

    return {
        'id': base_og.get('id'),
        'meta': base_og.get('meta'),
        'graph': mapper.digraph,
        'xref_graph': xref_graph,
        'graphdoc': obographdoc,
        'logical_definitions': logical_definitions
        }
