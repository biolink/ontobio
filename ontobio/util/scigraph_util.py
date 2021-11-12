"""
Utility functions for working with monarch identifiers using scigraph
"""
from typing import List, Dict, Iterator, Iterable, Optional
from json.decoder import JSONDecodeError

from ontobio.model.similarity import Node, TypedNode
from ontobio.neo.scigraph_ontology import RemoteScigraphOntology
from ontobio.util.user_agent import get_user_agent
from ontobio.model.bbop_graph import BBOPGraph
from ontobio.model.nlp import EntityAnnotationResults, SciGraphAnnotation
from ontobio.model.biomodel import BioObject, Taxon, NamedObject
from ontobio.config import get_config

from prefixcommons.curie_util import expand_uri
from dacite import from_dict
import requests
from requests import RequestException, HTTPError


# TODO: modularize into vocab/graph/etc?
HAS_PART = 'http://purl.obolibrary.org/obo/BFO_0000051'
INHERES_IN = 'http://purl.obolibrary.org/obo/RO_0000052'
INHERES_IN_PART_OF = 'http://purl.obolibrary.org/obo/RO_0002314'
HAS_ROLE = 'http://purl.obolibrary.org/obo/RO_0000087'
IN_TAXON = 'RO:0002162'
HAS_DISPOSITION = 'RO:0000091'
ENCODES = 'RO:0002205'
HAS_DBXREF = 'oboInOwl:hasDbXref'


class SciGraph:
    """
    Facade object for accessing a SciGraph instance.

    This provides access to both generic methods following a graph-oriented model, and
    domain-specific convenience methods that build in knowledge of different relationship types.

    """

    def __init__(self, url=None):
        if url is not None:
            self.url_prefix = url
        else:
            self.url_prefix = get_config()['scigraph_data']['url']

    def neighbors(self, id=None, **params):
        """
        Get neighbors of a node

        parameters are directly passed through to SciGraph: e.g. depth, relationshipType

        Returns a BBOPGraph
        """
        response = self.get_response("graph/neighbors", id, "json", **params)
        if response.status_code == 404:
            raise HTTPError

        return BBOPGraph(response.json())

    def node(self, id=None, **params):
        """
        Get a node in a graph plus its metadata

        Returns a BBOPGraph Node
        """
        response = self.get_response("graph", q=id, format="json", **params)
        if response.status_code == 404:
            raise HTTPError

        nodes = response.json()['nodes']
        if len(nodes) == 0:
            raise HTTPError

        return from_dict(NamedObject, nodes[0])

    def get_clique_leader(self, id) -> BioObject:
        """
        :raises NoResultFoundException
        :return: BioObject
        """
        response = self.get_response("dynamic/cliqueLeader", q=id, format="json")

        nodes = response.json()['nodes']
        if len(nodes) == 0:
            raise HTTPError

        return from_dict(BioObject, nodes[0])

    def bioobject(self, id, node_type=None, **params):
        """
        Get a node in a graph and translates it to biomodels datamodel

        Arguments
        ---------
        id
            identifier or CURIE

        class_name
            name of the class in the biomodel data model to instantiate

        Returns: biomodel.BioObject or subclass
        """
        bio_object = self.get_clique_leader(id)

        # get nodes connected with edge 'in_taxon'
        response = self.get_response(
            "graph/neighbors",
            q=bio_object.id,
            format="json",
            depth=1,
            relationshipType=IN_TAXON,
            direction="OUTGOING"
        )

        graph = BBOPGraph(response.json())

        bio_object.taxon = None
        for tax_edge in graph.edges:
            bio_object.taxon = from_dict(Taxon, graph.get_node(tax_edge.obj).as_dict())

        # Type specific
        if node_type == 'disease':
            # get nodes connected with edge 'has_disposition'
            response = self.get_response(
                "graph/neighbors",
                q=bio_object.id,
                format="json",
                depth=1,
                relationshipType=HAS_DISPOSITION,
                direction="OUTGOING"
            )
            graph = BBOPGraph(response.json())
            bio_object.inheritance = []
            bio_object.clinical_modifiers = []
            for disposition_edge in graph.edges:
                disposition = graph.get_node(disposition_edge.obj)
                if 'inheritance' in disposition.meta.category_list:
                    bio_object.inheritance.append(
                        from_dict(NamedObject, disposition.as_dict())
                    )
                else:
                    bio_object.clinical_modifiers.append(
                        from_dict(NamedObject, disposition.as_dict())
                    )

        return bio_object

    def graph(self, id=None):
        """
        Extracts a subgraph around a given in

        Graph includes superclass closure, equivalent classes and direct subclasses

        Returns a BBOPGraph
        """
        g1 = self.neighbors(id, relationshipType='subClassOf', blankNodes=False, direction='OUTGOING',depth=20)
        g2 = self.neighbors(id, relationshipType='subClassOf', direction='INCOMING', depth=1)
        g3 = self.neighbors(id, relationshipType='equivalentClass', depth=1)
        g1.merge(g2)
        g1.merge(g3)
        return g1

    # TODO: replace with https://github.com/SciGraph/SciGraph/issues/200
    def cbd(self, id=None):
        """
        Returns the Concise Bounded Description of a node

        See https://www.w3.org/Submission/CBD/
        """
        nodes = [id]
        g=BBOPGraph()
        while len(nodes)>0:
            n = nodes.pop()
            nextg = self.neighbors(n, params={'blankNodes':True, 'direction':'OUTGOING','depth':1})
            for nn in nextg.nodes:
                if nn.id.startswith("_:"):
                    n.append(nn.id)
            g.merge(nextg)
        return g

    def extract_subgraph(self, ids=None, relationshipType='subClassOf'):
        """
        Returns subgraph module extracted using list of node IDs as seed
        """
        ids = ids or []

        graph = BBOPGraph()
        visited = []
        while len(ids)>0:
            id = ids.pop()
            nextg = self.neighbors(id, blankNodes=False, relationshipType=relationshipType, direction='OUTGOING',depth=1)
            for edge in nextg.edges:
                next_id = edge.obj
                if next_id not in visited:
                    ids.append(next_id)
                    visited.append(next_id)
            graph.merge(nextg)
        return graph

    # TODO - direct SciGraph method?
    def traverse_chain(self, id=None, rels=None, type=None, blank=True, reverse_direction=False):
        """
        Finds all nodes reachable via a specified chain of relationship types
        """
        # we pop parts of the chain from a stack, so the
        # default direction is reversed, unless we
        # want to follow in the opposite direction

        rels = rels or []

        rels_ordered = rels.copy()
        if not reverse_direction:
            rels_ordered.reverse()

        direction = 'OUTGOING'
        if reverse_direction:
            direction = 'INCOMING'

        # list of tuples
        stack = [ (id, rels_ordered) ]

        nmap = {}
        sinks = []
        while len(stack)>0:
            (nextid, nextrels) = stack.pop()
            if len(nextrels) == 0:
                sinks.append(nextid)
            else:
                nextrel = nextrels.pop()
                nextg = self.neighbors(
                    nextid,
                    blankNodes=blank,
                    relationshipType=nextrel,
                    # works?
                    # See https://github.com/SciGraph/SciGraph/issues/135#issuecomment-305097228
                    entail=True,
                    direction=direction,
                    depth=1
                )
                for n in nextg.nodes:
                    nmap[n.id] = n
                for e in nextg.edges:
                    if not blank and e.obj.startswith(":"):
                        continue
                    stack.append( (e.obj, nextrels.copy()) )

        sinknodes = [nmap[x] for x in sinks]
        if type is not None:
            sinknodes = [x for x in sinknodes if type in x.meta.pmap['types']]

        return sinknodes


    def annotate_text(self, content, http_method='get', **args):
        """
        Directly wraps SciGraph annotations endpoint.
        Returns the text with annotated entities tagged as HTML <span>
        """

        params = {
            'content': content,
            **args
        }
        response = self.get_response("annotations", None, None, http_method, **params)
        return response.text

    def annotate_entities(self, content, http_method='get', **args):
        """
        Directly wraps SciGraph annotations/entities endpoint.
        """
        params = {
            'content': content,
            **args
        }
        response = self.get_response("annotations/entities", None, None, http_method, **params)
        scigraph_annotations = [from_dict(SciGraphAnnotation, annot) for annot in response.json()]
        return EntityAnnotationResults(scigraph_annotations, content)

    # Internal wrapper onto requests API
    def get_response(self, path="", q=None, format=None, http_method='get', **params):
        url = self.url_prefix + path
        if q is not None:
            url += "/" +q
        if format is not None:
            url = url  + "." + format
        if http_method == 'get':
            request = requests.get(url, params=params, headers={'User-Agent': get_user_agent(modules=[requests], caller_name=__name__)})
        elif http_method == 'post':
            request = requests.post(url, data=params, headers={'User-Agent': get_user_agent(modules=[requests], caller_name=__name__)})
        else:
            raise RequestException

        return request

    ## Domain-specific methods
    ## Note some of these may be redundant with https://github.com/monarch-initiative/monarch-cypher-queries/tree/master/src/main/cypher/golr-loader

    def gene_to_uniprot_proteins(self, id):
        """
        Given a gene ID, find the list of uniprot proteins that this encodes

        This method may be retired in future. See https://github.com/monarch-initiative/dipper/issues/461
        """
        uniprot_ids = []
        clique_leader = self.get_clique_leader(id)
        objs = self.traverse_chain(clique_leader.id, [ENCODES, HAS_DBXREF], blank=False, reverse_direction=False)
        for x in objs:
            if x.id.startswith('UniProtKB') and x.id not in uniprot_ids:
                uniprot_ids.append(x.id)
        return uniprot_ids

    def uniprot_protein_to_genes(self, id):
        """
        Given a UniProt ID, find the list of genes encoding this protein

        This method may be retired in future. See https://github.com/monarch-initiative/dipper/issues/461
        """
        encoding_nodes = self.neighbors(id,
                               blankNodes=False,
                               relationshipType=ENCODES,
                               # works?
                               # See https://github.com/SciGraph/SciGraph/issues/135#issuecomment-305097228
                               entail=True,
                               direction='INCOMING',
                               depth=1)
        genes = []
        for x in encoding_nodes.edges:
            genes.append(x.sub)

        # This second step is expensive and will no longer be required when
        # https://github.com/SciGraph/SciGraph/issues/135 is implemented
        gene_ids = []
        for geneId in genes:
            encoding_nodes = self.neighbors(
                geneId,
                blankNodes=False,
                relationshipType='equivalentClass',
                # See https://github.com/SciGraph/SciGraph/issues/135#issuecomment-305097228
                entail=True,
                direction='BOTH',
                depth=1
            )
            for x in encoding_nodes.edges:
                if x.sub not in gene_ids:
                    gene_ids.append(x.sub)

        return gene_ids

    def phenotype_to_entity_list(self, id):
        """
        Given a phenotype ID, find the list of affected entities

        Uses the Ontology Design Pattern has-part o inheres_in
        """
        inheres_in = self.traverse_chain(
            id,
            [HAS_PART, INHERES_IN],
            "anatomical entity"
        )
        inheres_in_part_of = self.traverse_chain(
            id,
            [HAS_PART, INHERES_IN_PART_OF],
            "anatomical entity"
        )
        objs = inheres_in + inheres_in_part_of

        return [from_dict(NamedObject, x.as_dict()) for x in objs]

    def substance_to_role_associations(self, id):
        """
        Given a chemical ID, find the list of roles

        Uses the Ontology Design Pattern CHEMICAL has-role ROLE
        """
        # TODO - include closure
        bbg = self.neighbors(id, relationshipType=HAS_ROLE, depth=1)
        return bbg_to_assocs(bbg)

    def substance_participates_in_associations(self, id):
        """
        Given a chemical ID, find the list of activities and processes that have this as participant

        Uses GO-CHEBI axioms
        """
        # TODO - include closure
        bbg = self.neighbors(id, direction='INCOMING', depth=1)
        return bbg_to_assocs(bbg)

    def get_datasets(self):
        """
        Get metadata about all the datasets in SciGraph
        """
        response = self.get_response("dynamic/datasets", None, "json")
        response_json = response.json()
        return response_json


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
    scigraph = RemoteScigraphOntology('scigraph:data')

    chunks = [id_list[i:i + 100] for i in range(0, len(list(id_list)), 100)]
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
        if not type_map[node['id']]:
            type_map[node['id']] = ['Node']

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


def bbg_to_assocs(g):
    return [bbedge_to_assoc(e,g) for e in g.edges]


def bbedge_to_assoc(e,g):
    return {
        'subject': {'id': e.sub,
                    'label': g.get_lbl(e.sub)
                    },
        'object': {'id': e.obj,
                   'label': g.get_lbl(e.obj)
                    },
        }
