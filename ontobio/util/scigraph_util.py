"""
Utility functions for working with monarch identifiers using scigraph
"""
from typing import List, Dict
from json.decoder import JSONDecodeError
from ontobio.ontol_factory import OntologyFactory
from ontobio.model.similarity import Node


def get_scigraph_nodes(**params)-> List[Dict]:
    """
    Queries scigraph neighbors to get a list of nodes back

    We use the scigraph neighbors function because ids can be sent in batch
    which is faster than iteratively querying solr search
    or the scigraph graph/id function

    :return: json decoded result from scigraph_ontology._neighbors_graph
    :raises ValueError: If id is not in scigraph
    """
    scigraph = OntologyFactory().create('scigraph:data')
    try:
        result_graph = scigraph._neighbors_graph(**params)
    except JSONDecodeError as exception:
        # Assume json decode is due to an incorrect class ID
        # Should we handle this?
        raise ValueError(exception.doc)

    return result_graph['nodes']


def get_id_type_map(id_list: List[str]) -> Dict[str, List[str]]:
    """
    Given a list of ids return their types

    :param id_list: list of ids
    :return: dictionary where the id is the key and the value is a list of types
    """
    type_map = {}
    filter_out_types = [
        'cliqueLeader',
        'Class',
        'Node',
        'Individual',
        'quality',
        'sequence feature'
    ]

    chunks = [id_list[i:i + 400] for i in range(0, len(id_list), 400)]
    for chunk in chunks:
        params = {
            'id': chunk,
            'depth': 0
        }

        for node in get_scigraph_nodes(**params):
            type_map[node['id']] = [typ.lower() for typ in node['meta']['types']
                                    if typ not in filter_out_types]

    return type_map


def get_nodes_from_ids(id_list: List[str]) -> List[Node]:
    """
    Given a list of ids return their types

    :param id_list: list of ids
    :return: dictionary where the id is the key and the value is a list of types
    """
    node_list = []

    chunks = [id_list[i:i + 400] for i in range(0, len(id_list), 400)]
    for chunk in chunks:
        params = {
            'id': chunk,
            'depth': 0
        }

        for result in get_scigraph_nodes(**params):
            if 'lbl' in result:
                label = [label for label in result['lbl'][0]]
            else:
                label = None # Empty string or None?
            node_list.append(Node(result['id'], label))

    return node_list
