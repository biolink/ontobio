import logging
import yaml
from marshmallow import Schema, fields, pprint, post_load

class ConfigSchema(Schema):
    """
    Marshmallow schema for configuration objects
    """
    sparql_url = fields.Url()
    solr_url = fields.Url()
    solr_search_url = fields.Url()
    go_solr_url = fields.Url()
    go_solr_search_url = fields.Url()
    
    @post_load
    def make_config(self, data):
        return Config(**data)
    
class Config():
    """
    A configuration object determines which external service URLs are used
    for different kinds of calls.

    """
    def __init__(self,
                 solr_assocs_url = "https://solr.monarchinitiative.org/solr/golr"
                 amigo_solr_assocs_url = "http://golr.berkeleybop.org"
                 solr_search_url = "https://solr-dev.monarchinitiative.org/solr/search"
                 amigo_solr_search_url = "http://golr.berkeleybop.org"
                 sparql_url = "http://sparql.hegroup.org/sparql"
                 use_amigo_for = "function"):
        self.solr_assocs_url = solr_assocs_url
        self.amigo_solr_assocs_url = amigo_solr_assocs_url
        self.solr_search_url = solr_assocs_url
        self.amigo_solr_search_url = amigo_solr_assocs_url
        self.sparql_url = sparql_url
        self.use_amigo_for = use_amigo_for

    def get_solr_search_url(use_amigo=False):
        """
        A solr search URL is used to search entities/concepts based on a limited set of parameters.

        There are two possible schemas: Monarch and AmiGO. These may converge in the future
        """
        url = self.solr_search_url
        if use_amigo:
            url = self.amigo_solr_search_url
        return url
            
    def get_solr_assocs_url(use_amigo=False):
        """
        A solr assocs URL is used to query triple-patterns in Solr, ie subject-relation-object

        There are two possible schemas: Monarch and AmiGO. The AmiGO schema is used for
        querying the GO and Planteome Golr instances
        """
        url = self.solr_assocs_url
        if use_amigo:
            url = self.amigo_solr_assocs_url
        return url

class Session():
    default_config_path = 'conf/config.yaml'
    config = None

session = Session()

def get_config():
    if session.config is None:
        logging.info("LOADING FROM: {}".format(session.default_config_path))
        session.config = load_config(session.default_config_path)
    else:
        logging.info("Using pre-loaded object: {}".format(session.config))
    return session.config

def load_config(path):
    f = open(path,'r')
    obj = yaml.load(f)
    schema = ConfigSchema()
    config = schema.load(obj)
    errs = schema.validate(obj)
    if len(errs) > 0:
        logging.error("ERRS: {}".format(errs))
        raise ValueError('Error loading '+path)
    #config = Config()
    return config
