from ontobio.config import get_config

from diskcache import Cache
import tempfile
import requests


cache = Cache(tempfile.gettempdir())


@cache.memoize()
def get_curie_map(url=None):
    """
    Get CURIE prefix map from SciGraph cypher/curies endpoint
    """
    if url is None:
        url = '{}/cypher/curies'.format(get_config().scigraph_data.url)
    response = requests.get(url)
    if response.status_code == 200:
        curie_map = response.json()
    else:
        curie_map = {}

    return curie_map
