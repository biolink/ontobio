from ontobio.config import get_config
from typing import List

config = get_config()
OWLSIM_URL = config['owlsim2']['url']
OWLSIM_TIMEOUT = config['owlsim2']['timeout']


def get_annotation_sufficiency(profile: List[str], owlsim):
    pass


