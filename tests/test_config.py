from ontobio.config import Config, get_config
import logging

def test_cfg():
    logging.info("TEST")
    cfg = get_config()
    logging.info("GOT: {}".format(cfg))
    print(str(cfg))
    assert True
    cfg = get_config()
    print(str(cfg.solr_assocs_url))
    print(str(cfg.ontologies))
