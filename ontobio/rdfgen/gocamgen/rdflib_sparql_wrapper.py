from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery
from ontobio.rdfgen.assoc_rdfgen import prefix_context


class RdflibSparqlWrapper:

    def run_query(self, graph: Graph, query):
        response = graph.query(prepareQuery(query, initNs=prefix_context))

        return response

    def find_involved_in_translated(self, graph: Graph, gp, term):
        # Recreate this query
        # query_pair = TriplePair((upt.molecular_function, ENABLED_BY, annoton.enabled_by),
        #                         (upt.molecular_function, PART_OF, term), connecting_entity=upt.molecular_function)
        query = """
            SELECT ?mf ?gp ?term
            WHERE {{
                ?mf rdf:type GO:0003674 .
                ?gp rdf:type {gp} .
                ?term rdf:type {term} .
                
                ?mf RO:0002333 ?gp .
                ?mf BFO:0000050 ?term
            }} 
        """.format(gp=gp, term=term)
        res = self.run_query(graph, query)
        return res

    def find_triple_by_class(self, graph: Graph, s="?any_s", p="?any_p", o="?any_o"):
        query = """
            SELECT *
            WHERE {{
                ?s rdf:type {s} .
                ?o rdf:type {o} .
                ?s {p} ?o
            }}
        """.format(s=s, p=p, o=o)
        res = self.run_query(graph, query)
        return res

    def find_acts_upstream_of_translated(self, graph, gp, causally_rel, term):
        # Recreate this query
        # query_pair = TriplePair((upt.molecular_function, ENABLED_BY, annoton.enabled_by),
        #                         (upt.molecular_function, causally_relation_uri, term),
        #                         connecting_entity=upt.molecular_function)
        query = """
            SELECT ?mf ?gp ?term
            WHERE {{
                ?mf rdf:type GO:0003674 .
                ?gp rdf:type {gp} .
                ?term rdf:type {term} .
                
                ?mf RO:0002333 ?gp .
                ?mf {causally_rel} ?term
            }}
        """.format(gp=gp, term=term, causally_rel=causally_rel)
        res = self.run_query(graph, query)
        return res

    def find_evidence_with(self, graph, annotated_source, annotated_property, annotated_target):
        # TODO: Just get all evidence properties e.g. contributors, date, reference
        query = """
            PREFIX lego: <http://geneontology.org/lego/>
        
            select *
            where {{
                ?source rdf:type {annotated_source} .
                ?target rdf:type {annotated_target} .
                                
                ?axiom owl:annotatedSource ?source .
                ?axiom owl:annotatedProperty {annotated_property} .
                ?axiom owl:annotatedTarget ?target .
                ?axiom lego:evidence ?evidence .
                
                ?evidence lego:evidence-with ?evi_with
            }}
        """.format(annotated_source=annotated_source, annotated_property=annotated_property, annotated_target=annotated_target)
        res = self.run_query(graph, query)
        return res

    def find_nested_location_chain(self, graph, primary_term_shape, *nested_terms):
        # nested_terms - Ordered list of chain elements including anchor term (e.g. root MF, primary CC)
        # Will look for chain of 'MF:root-occurs_in->term1-part_of->term2-part_of->term3-part_of->...'
        select_fields = []
        type_declarations = []
        location_edges = []
        type_declaration = "?loc_{} rdf:type {}"
        location_edge_pattern = "?loc_{} {} ?loc_{}"
        for idx, term in enumerate(nested_terms):
            term_ind_idx = idx+1
            select_fields.append("?loc_{}".format(term_ind_idx))
            type_declarations.append(type_declaration.format(term_ind_idx, term))
            edge_relation = "BFO:0000050"  # part_of
            # Here we use aspect to determine first edge_relation
            # This aspect param is a lazy hack because I haven't figured out how to do this directly in SPARQL
            if term_ind_idx == 1:
                if primary_term_shape in ["MolecularFunction", "BiologicalProcess"]:
                    edge_relation = "BFO:0000066"  # occurs_in
                elif primary_term_shape == "ProteinContainingComplex":
                    edge_relation = "RO:0001025"  # located_in
            if term_ind_idx < len(nested_terms):
                location_edges.append(location_edge_pattern.format(term_ind_idx, edge_relation, term_ind_idx+1))
        query = """
            SELECT {select_fields}
            WHERE {{
                {type_declarations} .

                {location_edges}
            }}
        """.format(select_fields=" ".join(select_fields), type_declarations=" .\n".join(type_declarations),
                   location_edges=" .\n".join(location_edges))
        # print(query)
        res = self.run_query(graph, query)
        return res
