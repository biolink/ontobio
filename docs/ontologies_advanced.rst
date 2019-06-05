.. _ontologies_advanced:

Advanced Ontology Use
=====================

The ontobio/config.yaml file contains settings which could be overidden (generally unnecessary).

Ignoring the Cache
------------------

Ontobio uses the Python Cachier library to enhance performance for some applications but there may be instances
when you wish to turn the caching off (e.g. if you are just reading a whole ontology into memory then working
with it, without modifying it or accessing it again from its remote source).  To disable caching, you set the
ignore_cache flag in the config.yaml file to 'True' (default: False).  The easiest, non-invasive way to achieve this
is to run this at a global location in your code during startup and before accessing any ontology:

::

    from ontobio.config import session
    session.config.ignore_cache = True
