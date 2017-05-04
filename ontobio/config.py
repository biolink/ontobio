import logging
import json

class Config():
    def __init__(self,
                 solr_url=None,
                 function_solr_url=None,
                 sparql_url=None):
        self.solr_url = solr_url
        self.function_solr_url = function_solr_url
        self.sparql_url = sparql_url

class Session():
    default_config_path = 'conf/config.yaml'
    config = None

session = Session()


def get_config():
    if session.config is None:
        logging.info("LOADING FROM: {}".format(default_config_path))
        session.config = load_config(session.default_config_path)
    return session.config

def load_config(path):
    #obj = json.loads(open(path,'r'))
    config = Config()
    return config
