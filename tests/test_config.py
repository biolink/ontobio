from ontobio.config import Config, get_config, set_config
import logging

def _endpoint(e):
    return "URL: {} OBJ: {}".format(e.url, str(e))

def test_cfg():
    logging.info("TEST")
    cfg = get_config()
    logging.info("GOT: {}".format(cfg))
    print(str(cfg))
    assert True
    #cfg = get_config()
    print("Main solr search: {}".format(_endpoint(cfg.solr_search)))
    print("Main solr assocs: {}".format(_endpoint(cfg.solr_assocs)))
    print("Pre-loaded ontologies: {}".format(cfg.ontologies))

    set_config('tests/resources/test-config.yaml')
    cfg = get_config()
    assert cfg.solr_assocs.url == "https://example.org"
