from enum import Enum

class UpperLevel():
    molecular_function = 'GO:0003674'
    biological_process = 'GO:0008150'
    cellular_component = 'GO:0005575'


class HpoUpperLevel(Enum):
    skeletal_system = 'HP:0000924'
    nervous_system  = 'HP:0000707'
    head_neck = 'HP:0000152'
    integument = 'HP:0001574'
    eye = 'HP:0000478'
    cardiovascular_system = 'HP:0001626'
    metabolism_homeostasis = 'HP:0001939'
    genitourinary_system = 'HP:0000119'
    digestive_system = 'HP:0025031'
    neoplasm = 'HP:0002664'
    blood = 'HP:0001871'
    immune_system = 'HP:0002715'
    endocrine = 'HP:0000818'
    musculature = 'HP:0003011'
    respiratory = 'HP:0002086'
    ear = 'HP:0000598'
    connective_tissue = 'HP:0003549'
    prenatal_or_birth = 'HP:0001197'
    growth = 'HP:0001507'
    breast = 'HP:0000769'
