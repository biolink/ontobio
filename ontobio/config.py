import logging
import yaml
import os
from marshmallow import Schema, fields, pprint, post_load

class OntologyConfigSchema(Schema):
    """
    Set of ontologies
    """
    id = fields.Str(description="local identifier")
    handle = fields.Str(description="ontology handle")
    pre_load = fields.Bool(description="if true, load this ontology at startup")

    @post_load
    def make_object(self, data):
        return OntologyConfig(**data)

class EndpointSchema(Schema):
    """
    Configuration for a REST or RESTish endpoint
    """
    url = fields.Url()
    timeout = fields.Int()

    @post_load
    def make_object(self, data):
        return Endpoint(**data)

class CategorySchema(Schema):
    """
    Maps a category label to a root ontology class
    """
    id = fields.Str()
    superclass = fields.Str()

    @post_load
    def make_object(self, data):
        return Category(**data)

class ConfigSchema(Schema):
    """
    Marshmallow schema for configuration objects.
    """
    sparql = fields.Nested(EndpointSchema, description="SPARQL URL to use for ontology queries")
    solr_assocs = fields.Nested(EndpointSchema)
    solr_search = fields.Nested(EndpointSchema)
    amigo_solr_assocs = fields.Nested(EndpointSchema)
    amigo_solr_search = fields.Nested(EndpointSchema)
    scigraph_ontology = fields.Nested(EndpointSchema)
    lay_person_search = fields.Nested(EndpointSchema)
    scigraph_data = fields.Nested(EndpointSchema)
    owlsim2 = fields.Nested(EndpointSchema)
    owlsim3 = fields.Nested(EndpointSchema)
    default_solr_schema = fields.Str()
    ontologies = fields.List(fields.Nested(OntologyConfigSchema))
    categories = fields.List(fields.Nested(CategorySchema))
    taxon_restriction = fields.List(fields.Str(description="taxon restriction"))
    use_amigo_for = fields.List(fields.Str(description="category to use amigo for"))

    @post_load
    def make_object(self, data):
        return Config(**data)

class Endpoint():
    """
    RESTish endpoint
    """
    def __init__(self,
                 url = None,
                 timeout = None):
        self.url = url
        self.timeout = timeout

class OntologyConfig():
    """
    Maps local id of ontology to a handle
    """
    def __init__(self,
                 id = None,
                 handle = None,
                 pre_load = False):
        self.id = id
        self.handle = handle
        self.pre_load  = pre_load

class Category():
    """
    Maps category to class
    """
    def __init__(self,
                 id = None,
                 superclass = None):
        self.id = id
        self.superclass = superclass

class Config():
    """
    A configuration object determines which external service URLs are used
    for different kinds of calls.

    """
    def __init__(self,
                 solr_assocs = None,
                 amigo_solr_assocs = None,
                 solr_search = None,
                 amigo_solr_search = None,
                 lay_person_search = None,
                 sparql = None,
                 scigraph_ontology = None,
                 scigraph_data = None,
                 owlsim2 = None,
                 owlsim3 = None,
                 ontologies = None,
                 categories = None,
                 default_solr_schema = None,
                 use_amigo_for = "function",
                 taxon_restriction = None):
        self.solr_assocs = solr_assocs
        self.amigo_solr_assocs = amigo_solr_assocs
        self.solr_search = solr_search
        self.amigo_solr_search = amigo_solr_search
        self.lay_person_search = lay_person_search
        self.sparql = sparql
        self.scigraph_ontology = scigraph_ontology
        self.scigraph_data = scigraph_data
        self.owlsim2 = owlsim2
        self.owlsim3 = owlsim3
        self.ontologies = ontologies
        self.categories = categories
        self.default_solr_schema = default_solr_schema
        self.use_amigo_for = use_amigo_for
        self.taxon_restriction = taxon_restriction

        if self.ontologies is None:
            self.ontologies = []

        if self.categories is None:
            self.categories = []

    def endpoint_url(self, endpoint):
        if endpoint is None:
            return None
        else:
            return endpoint.url

    def get_category_class(self, categ):
        matches = [c.superclass for c in self.categories if c.id == categ]
        if len(matches) > 0:
            return matches[0]
        return None

    def get_solr_search_url(self, use_amigo=False):
        """
        Return solr URL to be used for lexical entity searches

        A solr search URL is used to search entities/concepts based on a limited set of parameters.

        Arguments
        ---------
        use_amigo : bool
            If true, get the URL for the GO/AmiGO instance of GOlr. This is typically used for category='function' queries
        """
        url = self.endpoint_url(self.solr_search)
        if use_amigo:
            url = self.endpoint_url(self.amigo_solr_search)
        return url

    def get_solr_assocs_url(self, use_amigo=False):
        """
        Return solr URL to be used for assocation (enhanced triple) queries

        A solr assocs URL is used to query triple-patterns in Solr, ie subject-relation-object

        There are two possible schemas: Monarch and AmiGO. The AmiGO schema is used for
        querying the GO and Planteome Golr instances
        """
        url = self.endpoint_url(self.solr_assocs)
        if use_amigo:
            url = self.endpoint_url(self.amigo_solr_assocs)
        return url

class Session():
    """
    Configuration for current session
    """
    def __init__(self):
        self.default_config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "config.yaml"))
        self.config = None

"""
    Current session
"""
session = Session()

def get_config():
    """
    Return configuration for current session.

    When called for the first time, this will create a config object, using
    whatever is the default load path to find the config yaml
    """
    if session.config is None:
        path = session.default_config_path
        if os.path.isfile(path):
            logging.info("LOADING FROM: {}".format(path))
            session.config = load_config(path)
        else:
            session.config = Config()
            logging.info("using default session: {}, path does not exist: {}".format(session, path))
    else:
        logging.info("Using pre-loaded object: {}".format(session.config))
    return session.config

def set_config(path):
    """
    Set configuration for current session.
    """
    logging.info("LOADING FROM: {}".format(path))
    session.config = load_config(path)
    return session.config

def reset_config():
    """
    Reset currrent session configuration
    """
    session.config = None

def load_config(path):
    f = open(path,'r')
    obj = yaml.load(f, Loader=yaml.FullLoader)
    schema = ConfigSchema()
    config = schema.load(obj).data
    errs = schema.validate(obj)
    if len(errs) > 0:
        logging.error("CONFIG ERRS: {}".format(errs))
        raise ValueError('Error loading '+path)
    #config = Config()
    return config
