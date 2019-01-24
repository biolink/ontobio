from ontobio.ontol_factory import OntologyFactory


class GoAspector:
    def __init__(self, go_ontology):
        if go_ontology:
            self.ontology = go_ontology
        else:
            self.ontology = OntologyFactory().create("go")

    def get_ancestors_through_subont(self, go_term, relations):
        """
        Returns the ancestors from the relation filtered GO subontology of go_term's ancestors.

        subontology() primarily used here for speed when specifying relations to traverse. Point of this is to first get
        a smaller graph (all ancestors of go_term regardless of relation) and then filter relations on that instead of
        the whole GO.
        """
        all_ancestors = self.ontology.ancestors(go_term, reflexive=True)
        subont = self.ontology.subontology(all_ancestors)
        return subont.ancestors(go_term, relations)

    def get_isa_partof_closure(self, go_term):
        return self.get_ancestors_through_subont(go_term, relations=["subClassOf", "BFO:0000050"])

    def get_isa_closure(self, go_term):
        return self.get_ancestors_through_subont(go_term, relations=["subClassOf"])

    def is_biological_process(self, go_term):
        """
        Returns True is go_term has is_a, part_of ancestor of biological process GO:0008150
        """
        bp_root = "GO:0008150"
        if go_term == bp_root:
            return True
        ancestors = self.get_isa_closure(go_term)
        if bp_root in ancestors:
            return True
        else:
            return False

    def is_molecular_function(self, go_term):
        """
        Returns True is go_term has is_a, part_of ancestor of molecular function GO:0003674
        """
        mf_root = "GO:0003674"
        if go_term == mf_root:
            return True
        ancestors = self.get_isa_closure(go_term)
        if mf_root in ancestors:
            return True
        else:
            return False

    def is_cellular_component(self, go_term):
        """
        Returns True is go_term has is_a, part_of ancestor of cellular component GO:0005575
        """
        cc_root = "GO:0005575"
        if go_term == cc_root:
            return True
        ancestors = self.get_isa_closure(go_term)
        if cc_root in ancestors:
            return True
        else:
            return False

    def go_aspect(self, go_term):
        """
        For GO terms, returns F, C, or P corresponding to its aspect
        """
        if not go_term.startswith("GO:"):
            return None
        else:
            # Check ancestors for root terms
            if self.is_molecular_function(go_term):
                return 'F'
            elif self.is_cellular_component(go_term):
                return 'C'
            elif self.is_biological_process(go_term):
                return 'P'
