"""
Utility functions for working with monarch identifiers using scigraph
"""
from typing import List, Dict, Iterator, Iterable, Optional
from json.decoder import JSONDecodeError
from ontobio.ontol_factory import OntologyFactory
from ontobio.model.similarity import Node, TypedNode


def namespace_to_taxon() -> Dict[str, Node]:
    """
    namespace to taxon mapping
    """
    human_taxon = Node(
        id='NCBITaxon:9606',
        label='Homo sapiens'
    )
    return {
        'MGI': Node(
            id='NCBITaxon:10090',
            label='Mus musculus'
        ),
        'MONDO':   human_taxon,
        'OMIM':    human_taxon,
        'MONARCH': human_taxon,
        'HGNC':    human_taxon,
        'FlyBase': Node(
            id='NCBITaxon:7227',
            label='Drosophila melanogaster'
        ),
        'WormBase': Node(
            id='NCBITaxon:6239',
            label='Caenorhabditis elegans'
        ),
        'ZFIN': Node(
            id='NCBITaxon:7955',
            label='Danio rerio'
        )
    }


def get_scigraph_nodes(id_list)-> Iterator[Dict]:
    """
    Queries scigraph neighbors to get a list of nodes back

    We use the scigraph neighbors function because ids can be sent in batch
    which is faster than iteratively querying solr search
    or the scigraph graph/id function

    :return: json decoded result from scigraph_ontology._neighbors_graph
    :raises ValueError: If id is not in scigraph
    """
    scigraph = OntologyFactory().create('scigraph:data')

    chunks = [id_list[i:i + 400] for i in range(0, len(list(id_list)), 400)]
    for chunk in chunks:
        params = {
            'id': chunk,
            'depth': 0
        }

        try:
            result_graph = scigraph._neighbors_graph(**params)
            for node in result_graph['nodes']:
                yield node
        except JSONDecodeError as exception:
            # Assume json decode is due to an incorrect class ID
            # Should we handle this?
            raise ValueError(exception.doc)


def get_id_type_map(id_list: Iterable[str]) -> Dict[str, List[str]]:
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

    for node in get_scigraph_nodes(id_list):
        type_map[node['id']] = [typ.lower() for typ in node['meta']['types']
                                if typ not in filter_out_types]

    return type_map


def get_nodes_from_ids(id_list: Iterable[str]) -> List[Node]:
    """
    Given a list of ids return their types

    :param id_list: list of ids
    :return: dictionary where the id is the key and the value is a list of types
    """
    node_list = []

    for result in get_scigraph_nodes(id_list):
        if 'lbl' in result:
            label = result['lbl']
        else:
            label = None  # Empty string or None?
        node_list.append(Node(result['id'], label))

    return node_list


def get_taxon(id: str) -> Optional[Node]:
    """
    get taxon for id

    Currently via hardcoding, should replace when scigraph when
    taxa are more universally annotated (having these as node
    properties would also be more performant)

    :param id: curie formatted id
    :return: Node where id is the NCBITaxon curie and label is the scientific name
    """
    taxon = None
    namespace = id.split(":")[0]
    if namespace in namespace_to_taxon():
        taxon = namespace_to_taxon()[namespace]

    return taxon


def typed_node_from_id(id: str) -> TypedNode:
    """
    Get typed node from id

    :param id: id as curie
    :return: TypedNode object
    """
    filter_out_types = [
        'cliqueLeader',
        'Class',
        'Node',
        'Individual',
        'quality',
        'sequence feature'
    ]
    node = next(get_scigraph_nodes([id]))

    if 'lbl' in node:
        label = node['lbl']
    else:
        label = None  # Empty string or None?

    types = [typ.lower() for typ in node['meta']['types']
             if typ not in filter_out_types]

    return TypedNode(
        id=node['id'],
        label=label,
        type=types[0],
        taxon = get_taxon(id)
    )
