import json
from typing import Dict, NewType, List

from ontobio.model.association import GoAssociation, gp_type_label_to_curie

class Entity(dict):

    def __init__(self, d):
        super(Entity, self).__init__(d)

    def __hash__(self):
        d = json.dumps(self, sort_keys=True)
        return hash(d)


class GafGpiBridge(object):

    def __init__(self):
        self.cache = []

    def convert_association(self, association, gpad_gpi_output_version) -> Entity:
        """
        'id' is already `join`ed in both the Association and the Entity,
        so we don't have to worry about what that looks like. We assume
        it's correct.

        :param association: GoAssociation
        :param gpad_gpi_output_version: str value of the GPAD/GPI version to write - either 2.0 or 1.2
        :return: Entity
        """
        if isinstance(association, GoAssociation):
            if gpad_gpi_output_version == "2.0":
                # print(json.dumps(association, indent=4))
                gpi_obj = {
                    'id': str(association.subject.id),
                    'label': association.subject.label,  # db_object_symbol,
                    'full_name': association.subject.fullname,  # db_object_name,
                    'synonyms': association.subject.synonyms,
                    'type': [gp_type_label_to_curie(association.subject.type[0])], #db_object_type,
                    'parents': "", # GAF does not have this field, but it's optional in GPI
                    'xrefs': "", # GAF does not have this field, but it's optional in GPI
                    'taxon': {
                        'id': str(association.subject.taxon)
                    },
                    'encoded_by': "" # GAF does not have this field, but it's optional in GPI

                }
                return Entity(gpi_obj)
            else:
                gpi_obj = {
                    'db': str(association.subject.id.split(":")[0]),
                    'id': str(association.subject.id.split(":")[1]),
                    'label': association.subject.label,  # db_object_symbol,
                    'full_name': association.subject.fullname,  # db_object_name,
                    'synonyms': association.subject.synonyms,
                    'type': [gp_type_label_to_curie(association.subject.type[0])],  # db_object_type,
                    'parents': "",  # GAF does not have this field, but it's optional in GPI
                    'xrefs': "",  # GAF does not have this field, but it's optional in GPI
                    'taxon': {
                        'id': str(association.subject.taxon)
                    },
                    'encoded_by': ""  # GAF does not have this field, but it's optional in GPI

                }
                return Entity(gpi_obj)

        return None

    def entities(self) -> List[Entity]:
        return list(self.cache)
