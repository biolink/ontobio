from ontobio.rdfgen.gocamgen.utils import contract_uri_wrapper

### Simple example: 'GP --enabled_by--> MF --part_of--> BP'
### First find all 'GP --enabled_by--> MF' triples
### Then find a 'MF --part_of--> BP' where URI of MF equals URI of MF of any of triples in first set.
### So subsequent links (triples) in the chain will be passed the whole set of candidate preceding chains
### As long as current triple matches next link in pattern and URI of subject matches URI of previous triple's object, keep going


class TriplePattern:
    def __init__(self, ordered_triples):
        self.ordered_triples = ordered_triples


class ConnectedTriplePattern(TriplePattern):
    def __init__(self, ordered_triples):
        TriplePattern.__init__(self, ordered_triples)


class TriplePair:
    def __init__(self, triple_a, triple_b, connecting_entity):
        self.triples = (triple_a, triple_b)
        # Check to make sure connecting_entity is in both triples
        self.connecting_entity = connecting_entity

    def is_connected_by_uri(self, model):
        #TODO Check that subjects and objects are URIs
        for uri in [self.triples[0][0], self.triples[0][2]]:
            class_curie = model.class_for_uri(uri)
            if class_curie == self.connecting_entity and uri in self.triples[1]:
                return True
        return False

    def connecting_entity_uri(self, model):
        # entity is either [0] or [2] of either self.triples[0] or self.triples[1]
        # Scan these, checking class_for_uri == connecting_entity
        for uri in [self.triples[0][0], self.triples[0][2], self.triples[1][0], self.triples[1][2]]:
            class_curie = model.class_for_uri(uri)
            if class_curie == self.connecting_entity:
                return uri
        return None

# AKA pattern? Holds all pairs and will be query input for TriplePatternFinder
class TriplePairCollection:
    def __init__(self):
        self.chain_collection = []


class TriplePatternFinder:

    def find_pattern_recursive(self, model, pattern: TriplePattern, candidate_chains=[], exact_length=False,
                               pattern_length=None):
        # break down pattern into component triples
        p = pattern.ordered_triples[0]
        found_triples = model.triples_by_ids(*p)

        if len(found_triples) > 0:
            if len(candidate_chains) == 0:
                # This is start of chain
                # candidate_chains = [[t] for t in found_triples]
                candidate_chains = []
                for t in found_triples:
                    if exact_length and len(pattern.ordered_triples) == 1:
                        if self.triple_individuals_only_in_chain(model, [t], t):
                            # stuff is gonna start on fire
                            fire = "started"
                            candidate_chains.append([t])
                    else:
                        candidate_chains.append([t])
                if pattern_length is None:
                    pattern_length = len(pattern.ordered_triples)
            else:
                candidate_chains_local = []
                for chain in candidate_chains:
                    for triple in found_triples:
                        #TODO: Make more selective (e.g. subject or object must be in previous triple)
                        if exact_length and len(pattern.ordered_triples) == 1:
                            # This is the last triple in chain. More checks needed. Triple connected to other triples?
                            subject_triples = model.triples_involving_individual(triple[0])
                            object_triples = model.triples_involving_individual(triple[2])
                            # Er, ANY other triples with subject or object?
                            # Any of these contain triples not in chain?
                            drop_chain = False
                            for t in subject_triples + object_triples:
                                if t not in chain:
                                    drop_chain = True
                            if not drop_chain:
                                candidate_chains_local.append(chain + [triple])
                        else:
                            candidate_chains_local.append(chain + [triple])
                candidate_chains = candidate_chains_local

            if len(pattern.ordered_triples) > 1:
                rest_of_pattern = TriplePattern(pattern.ordered_triples[1:len(pattern.ordered_triples)])
                candidate_chains = self.find_pattern_recursive(model, rest_of_pattern, candidate_chains,
                                                               exact_length=exact_length, pattern_length=pattern_length)
            elif exact_length:
                # On last triple of pattern. Throw out chains with len() != len(starting_pattern)
                candidate_chains_local = []
                for chain in candidate_chains:
                    # And end triple of chain
                    if len(chain) == pattern_length:
                        candidate_chains_local.append(chain)
                candidate_chains = candidate_chains_local
        else:
            candidate_chains = []

        return candidate_chains

    # def find_connected_pattern(self, model: AssocGoCamModel, pair_collection: TriplePairCollection, candidate_chains=[]):
    def find_connected_pattern(self, model, pair_collection: TriplePairCollection, exact=False):
        # pair_collection is a TriplePairCollection w/ chain_collection of TriplePair[]. Each of these TriplePairs
        # consists of two triples, e.g. ("MF-term", relation_uri, "GP-class")
        # Returned output should be a TriplePairCollection w/ chain_collection of TriplePairs consisting of all-URI triples.
        connected_pair_collection = TriplePairCollection()  # will be triples of URIs
        for pair in pair_collection.chain_collection:
            pattern = TriplePattern([*pair.triples])
            found_pairs = self.find_pattern_recursive(model, pattern)  # only using this 2-deep
            connected_pair = None
            for fpair in found_pairs:
                # fpair is list of two triples
                #TODO put into TriplePairs
                f_triple_pair = TriplePair(*fpair, connecting_entity=pair.connecting_entity)
                if f_triple_pair.is_connected_by_uri(model):
                    connected_pair = f_triple_pair
                    break
            if connected_pair:
                connected_pair_collection.chain_collection.append(connected_pair)
            else:
                # TODO: Should this return 'connected_pair_collection' instead?
                return None
        return connected_pair_collection

    def triple_individuals_only_in_chain(self, model, chain, triple):
        # This is the last triple in chain. More checks needed. Triple connected to other triples?
        subject_triples = model.triples_involving_individual(triple[0])
        object_triples = model.triples_involving_individual(triple[2])
        # Er, ANY other triples with subject or object?
        # Any of these contain triples not in chain?
        for t in subject_triples + object_triples:
            relation_curie = contract_uri_wrapper(t[1])[0]
            # We basically just want to look at RO, BFO relations
            if not (relation_curie.startswith("RO:") or relation_curie.startswith("BFO:")):
                continue
            if t not in chain:
                return False
        return True
