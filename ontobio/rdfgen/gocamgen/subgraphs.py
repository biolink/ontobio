from networkx import MultiDiGraph
from rdflib.term import URIRef
from ontobio.rdfgen.gocamgen.rdflib_sparql_wrapper import RdflibSparqlWrapper
from ontobio.rdfgen.gocamgen.utils import expand_uri_wrapper
from ontobio.rdfgen.gocamgen.errors import ModelRdfWriteException
import logging

logger = logging.getLogger(__name__)

# How do we track/compare fully built annotations before adding to model? We need a separate
# subgraph for each assertion (no IRIs, just classes)
# These subgraphs get parsed into SPARQL queries.
#
# Number each instance like so:
# GO:0003674-1 enabled_by WB:WBGene00001173-1
# GO:0003674-1 part_of GO:0051343-1
# GO:0003674-1 has_input WB:WBGene00001173-2
# GO:0003674-1 causally_upstream_of GO:0003674-2
# GO:0003674-2 enabled_by WB:WBGene00001173-2
# Are there any "-"s in identifiers?


class AnnotationSubgraph(MultiDiGraph):

    def __init__(self):
        MultiDiGraph.__init__(self)
        self.class_counts = {}

    def add_edge(self, u_for_edge, relation, v_for_edge, key=None, **attr):
        attr["relation"] = relation
        MultiDiGraph.add_edge(self, u_for_edge, v_for_edge, key, **attr)

    # Will turn input of GO:0045944 into node_id=GO:0045944-1, sparql_var=GO_0045944_1
    # Will turn input of MGI:MGI:98956 into node_id=MGI:MGI:98956-1, sparql_var=MGI_MGI_98956_1
    # Ex:
    # >>> g.nodes['GO:0045944-1']
    # {'sparql_var': 'GO_0045944_1'}
    # Returns the networkx graph node ID used in tracking instances
    # Use this node ID to get instance IRI (once it's defined) and SPARQL variable name
    def add_instance_of_class(self, class_id, is_anchor=False, negated=False):
        if negated:
            class_id = "NOT-{}".format(class_id)
        next_num = self.increment_class_count(class_id)
        node_id = "{}-{}".format(class_id, next_num)
        # TODO: Maybe sparql_var doesn't need to be stored and can always be parsed out of node_id? Make function
        sparql_var = node_id.replace(":", "_")
        sparql_var = sparql_var.replace("-", "_")
        self.add_node(node_id, sparql_var=sparql_var)
        if is_anchor:
            self.set_anchor(node_id)

        return node_id

    def increment_class_count(self, class_id):
        if class_id not in self.class_counts:
            self.class_counts[class_id] = 0
        self.class_counts[class_id] += 1
        return self.class_counts[class_id]

    # Anchor is used for tracking which instance to hang extensions from
    def set_anchor(self, node_id):
        # Reset all nodes
        for n in self:
            is_anchor = self.nodes[n].get("is_anchor")
            if is_anchor:
                self.nodes[n]["is_anchor"] = None
        # Mark this node_id as anchor
        self.nodes[node_id]["is_anchor"] = True

    def get_anchor(self):
        for n in self:
            is_anchor = self.nodes[n].get("is_anchor")
            if is_anchor:
                return n

    def node_sparql_variable(self, node):
        return self.nodes[node]["sparql_var"]

    def node_instance_iri(self, node):
        return self.nodes[node].get("instance_iri")

    def print_edges(self):
        for u, v, relation in self.edges(data="relation"):
            print("{} {} {}".format(u, relation, v))

    def generate_sparql_representation(self):
        conditions = []
        for n in self:
            type_declaration = "?{} rdf:type {}".format(self.node_sparql_variable(n), self.node_class(n))
            conditions.append(type_declaration)
        # TODO: Check that order of assertion triples in SPARQL doesn't affect result
        for u, v, relation in self.edges(data="relation"):
            assert_declaration = "?{} {} ?{}".format(self.node_sparql_variable(u), relation, self.node_sparql_variable(v))
            conditions.append(assert_declaration)

        return " .\n".join(conditions)

    def find_matches_in_model(self, model):
        sparql_wrapper = RdflibSparqlWrapper()
        query = """
                    select *
                    WHERE {{
                        {}
                    }}
                """.format(self.generate_sparql_representation())
        return sparql_wrapper.run_query(model.graph, query)

    def print_matches_in_model(self, model):
        # For debugging
        response = self.find_matches_in_model(model)

        if len(response) > 0:
            count = 1
            for res in response:
                print("Result {}:".format(count))
                for n in self:
                    instance_iri = res[self.node_sparql_variable(n)]
                    print("{} - {}".format(n, instance_iri))
                count += 1

    def write_to_model(self, model, evidences, reuse_existing=False):
        # Handles reusing found subgraph IRIs as well as inserting all new individuals
        axiom_ids = []
        exact_match = None
        response = []
        if reuse_existing:
            response = self.find_matches_in_model(model)
        if len(response) > 0:
            for res in response:
                # TODO: First check that these are "exact" subgraph matches, meaning match result isn't subgraph of other annotation.
                exact_match = res
                break
        if exact_match:
            # Update rdflib.Graph - just add evidence to all edges/axioms
            # Collect axiom_ids to add evidence to
            for u, v, relation in self.edges(data="relation"):
                subject_instance_iri = exact_match[self.node_sparql_variable(u)]
                object_instance_iri = exact_match[self.node_sparql_variable(v)]
                self.nodes[u]["instance_iri"] = subject_instance_iri
                self.nodes[v]["instance_iri"] = object_instance_iri
                relation_uri = expand_uri_wrapper(relation)
                axiom_ids.append(model.find_bnode((self.node_instance_iri(u),
                                                   URIRef(relation_uri),
                                                   self.node_instance_iri(v))))
        else:
            # Insert into rdflib.Graph - everything is new
            pattern = self.generate_sparql_representation()
            # No. Need to invent IRIs for individuals.
            # Can we reuse model.declare_individual, add_axiom stuff? Probably.
            for u, v, relation in self.edges(data="relation"):
                subject_instance_iri = self.node_instance_iri(u)
                if subject_instance_iri is None:
                    subject_instance_iri = model.declare_individual(self.node_class(u), evidences=evidences, negated=u.startswith("NOT-"))
                    self.nodes[u]["instance_iri"] = subject_instance_iri
                object_instance_iri = self.node_instance_iri(v)
                if object_instance_iri is None:
                    object_instance_iri = model.declare_individual(self.node_class(v), evidences=evidences, negated=v.startswith("NOT-"))
                    self.nodes[v]["instance_iri"] = object_instance_iri
                try:
                    relation_uri = expand_uri_wrapper(relation)
                except AttributeError as ex:
                    exception_message = "Unparseable relation: {relation} from triple {u} {relation} {v} in model {modeltitle}".format(
                        relation=relation, u=u, v=v, modeltitle=model.modeltitle)
                    logger.info(exception_message)
                    raise ModelRdfWriteException(exception_message)
                axiom_ids.append(model.add_axiom(model.writer.emit(subject_instance_iri,
                                                                   URIRef(relation_uri),
                                                                   object_instance_iri)))
        # Add the evidences to whatever axioms we got
        for axiom_id in axiom_ids:
            model.add_evidences(axiom_id, evidences)

    @staticmethod
    def node_class(node):
        # Gotta handle things like: NOT-GO:1234567-1, GO:1234567-2, MGI:MGI:4657382-1
        node = node.lstrip("NOT-")
        return "-".join(node.split("-")[0:-1])
