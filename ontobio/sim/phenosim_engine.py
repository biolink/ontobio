from ontobio.sim.api.interfaces import SimApi
from typing import Iterable, Dict, Union, Optional, List
from ontobio.model.similarity import SimResult, TypedNode
from ontobio.vocabulary.similarity import SimAlgorithm
from ontobio.sim.api.interfaces import FilteredSearchable
from ontobio.golr.golr_associations import get_objects_for_subject
from ontobio.util.scigraph_util import get_id_type_map, typed_node_from_id


class PhenoSimEngine():
    """
    Engine for computing phenotype similarity

    A wrapper for a similarity API whereby non-phenotype identifiers
    are resolved to a list of phenotypes
    """

    def __init__(self, sim_api: SimApi):
        self.sim_api = sim_api

    def search(
            self,
            id_list: List[str],
            negated_ids: Optional[List] = None,
            limit: Optional[int] = 100,
            taxon_filter: Optional[int]= None,
            category_filter: Optional[str]= None,
            method: Optional[SimAlgorithm] = SimAlgorithm.PHENODIGM
    ) -> SimResult:
        """
        Execute a search using sim_api, resolving non-phenotype ids to
        phenotype lists then adding them to the profile (eg genes, diseases)

        :raises NotImplementedError:
            - If sim method or filters are not supported
        """

        if negated_ids is None: negated_ids = []

        if method not in self.sim_api.matchers():
            raise NotImplementedError("Sim method not implemented "
                                      "in {}".format(str(self.sim_api)))

        # Determine if entity is a phenotype or individual containing
        # a pheno profile (gene, disease, case, etc)
        pheno_list = PhenoSimEngine._resolve_nodes_to_phenotypes(id_list)

        if taxon_filter is not None or category_filter is not None:
            if not isinstance(self.sim_api, FilteredSearchable):
                raise NotImplementedError("filtered search not implemented "
                                          "in {}".format(str(self.sim_api)))
            search_result = self.sim_api.filtered_search(
                pheno_list, negated_ids, limit, taxon_filter, category_filter, method
            )
        else:
            search_result = self.sim_api.search(pheno_list, negated_ids, limit, method)

        return search_result

    def compare(self,
                reference_ids: List,
                query_profiles: List[List],
                method: Optional[SimAlgorithm] = SimAlgorithm.PHENODIGM) -> SimResult:
        """
        Execute one or more comparisons using sim_api
        :param reference_ids: a list of phenotypes or ids that comprise
                              one or more phenotypes
        :param query_profiles: a list of lists of phenotypes or ids
                                   that comprise one or more phenotypes
        :param method: comparison method
        :return: SimResult object
        :raises NotImplementedError: If sim method or filters are not supported
        """
        if method not in self.sim_api.matchers():
            raise NotImplementedError("Sim method not implemented "
                                      "in {}".format(str(self.sim_api)))

        is_first_result = True
        comparisons = None

        reference_phenos = PhenoSimEngine._resolve_nodes_to_phenotypes(reference_ids)
        for query_profile in query_profiles:
            query_phenos = PhenoSimEngine._resolve_nodes_to_phenotypes(query_profile)
            sim_result = self.sim_api.compare(reference_phenos, query_phenos, method)
            if len(query_profile) > 1:
                id = " + ".join(query_profile)
                sim_result.matches[0].id = id
                sim_result.matches[0].label = id
            else:
                node = typed_node_from_id(query_profile[0])
                sim_result.matches[0].id = node.id
                sim_result.matches[0].label = node.label
                sim_result.matches[0].type = node.type
                sim_result.matches[0].taxon = node.taxon

            if is_first_result:
                comparisons = sim_result
                is_first_result = False
            else:
                comparisons.matches.append(sim_result.matches[0])
                comparisons.query.target_ids.append(sim_result.query.target_ids[0])

        if len(reference_ids) == 1:
            comparisons.query.reference = typed_node_from_id(reference_ids[0])
        else:
            reference_id = " + ".join(reference_ids)
            comparisons.query.reference = TypedNode(
                id=reference_id,
                label=reference_id,
                type='unknown'
            )

        return comparisons

    @staticmethod
    def _resolve_nodes_to_phenotypes(id_list: List[str]) -> List[str]:
        """
        Given a list of ids of unknown type, determine which ids
        are phenotypes, if the id is not a phenotype, check to
        see if it is associated with one or more phenotypes via
        the 'has_phenotype' relation
        :param id_list: list of ids of any type (curies as strings)
        :return: list of phenotypes (curies as strings)
        """
        pheno_list = []
        node_types = get_id_type_map(id_list)

        for node in id_list:
            if 'phenotype' in node_types[node]:
                pheno_list.append(node)
            else:
                phenotypes = get_objects_for_subject(
                    subject=node, object_category='phenotype', relation='RO:0002200'
                )
                pheno_list = pheno_list + phenotypes
        return pheno_list

    @staticmethod
    def _get_node_info(id_list: List[str]) -> List[str]:
        """
        Given a list of ids of unknown type, determine which ids
        are phenotypes, if the id is not a phenotype, check to
        see if it is associated with one or more phenotypes via
        the 'has_phenotype' relation
        :param id_list: list of ids of any type (curies as strings)
        :return: list of phenotypes (curies as strings)
        """
        pheno_list = []
        node_types = get_id_type_map(id_list)

        for node in id_list:
            if 'phenotype' in node_types[node]:
                pheno_list.append(node)
            else:
                phenotypes = get_objects_for_subject(
                    subject=node, object_category='phenotype', relation='RO:0002200'
                )
                pheno_list = pheno_list + phenotypes
        return pheno_list
