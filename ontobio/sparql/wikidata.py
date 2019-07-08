"""
Wrap WD sparql
"""

from SPARQLWrapper import SPARQLWrapper, JSON
from prefixcommons.curie_util import contract_uri, expand_uri
from functools import lru_cache
import networkx
from cachier import cachier
import datetime
import logging

SHELF_LIFE = datetime.timedelta(days=7)

# CACHE STRATEGY:
# by default, the cache is NOT persistent. Only single threaded clients should
# call a cached method with writecache=True.
# Note we are layering the in-memory cache over the persistent cache

cache = lru_cache(maxsize=None)
#cache = cachier(stale_after=SHELF_LIFE)

LIMIT = 200000

prefixmap = dict(
    HP = 'http://www.wikidata.org/prop/direct/P3841',
    ENVO = 'http://www.wikidata.org/prop/direct/P3859',
    DOID = 'http://www.wikidata.org/prop/direct/P699',
    CHEBI = 'http://www.wikidata.org/prop/direct/P683',
    UniProtKB = 'http://www.wikidata.org/prop/direct/P352',
    NCBIGene = 'http://www.wikidata.org/prop/direct/P351',
    IPR = 'http://www.wikidata.org/prop/direct/P2926',
    encodes = 'http://www.wikidata.org/prop/direct/P688',
    genetic_association = 'http://www.wikidata.org/prop/direct/P2293',
    treated_by_drug = 'http://www.wikidata.org/prop/direct/P2176')

qmap = dict(
    disease2protein = dict(chain=['genetic_association', 'encodes'], prefix='UniProtKB'),
    disease2drug = dict(chain=['treated_by_drug']),
    genetic_association = dict(chain=['genetic_association'], prefix='NCBIGene')
    )


class Properties:
    """
    Common SPARQL prefixes used by wikidata.

    Note we use the "trick" whereby an entire property URI can be encoded as a prefix.
    """
    def prefixes(self):
        return [attr for attr in dir(self) if not callable(getattr(self,attr)) and not attr.startswith("__")]
    def get_uri(self, pfx):
        return vars(PrefixMap).get(pfx)
    def gen_header(self):
        return "\n".join(["prefix {}: <{}>".format(attr,self.get_uri(attr)) for attr in self.prefixes()])

    DOID = 'http://www.wikidata.org/prop/direct/P699'
    CHEBI = 'http://www.wikidata.org/prop/direct/P683'

def run_sparql(q):
    # TODO: select endpoint based on ontology
    logging.info("Connecting to sparql endpoint...")
    sparql = SPARQLWrapper("http://query.wikidata.org/sparql")
    logging.info("Made wrapper: {}".format(sparql))
    # TODO: iterate over large sets?
    full_q = q + ' LIMIT ' + str(LIMIT)
    sparql.setQuery(q)
    sparql.setReturnFormat(JSON)
    logging.info("Query: {}".format(q))
    results = sparql.query().convert()
    bindings = results['results']['bindings']
    logging.info("Rows: {}".format(len(bindings)))
    for r in bindings:
        curiefy(r)
    return bindings

def curiefy(r):
    for (k,v) in r.items():
        if v['type'] == 'uri':
            curies = contract_uri(v['value'])
            if len(curies)>0:
                r[k]['value'] = curies[0]

def ensure_prefixed(x, prefix):
    if not x.startswith(prefix):
        x = prefix + ':' + x
    return x
                
def fetchall_xrefs(prefix):
    m = {}
    pairs = fetchall_triples_xrefs(prefix)
    if len(pairs) == LIMIT:
        logging.error("Too many: {} {}".format(LIMIT, pairs[:10]))
        return None
    for (c,x) in pairs:
        if not x.startswith(prefix):
            x = prefix + ':' + x
        if x not in m:
            m[x] = []
        m[x].append(c)
    return m

@cachier(stale_after=SHELF_LIFE)
def fetchall_triples_xrefs(prefix):
    """
    fetch all xrefs for a prefix, e.g. CHEBI
    """
    logging.info("fetching xrefs for: "+prefix)
    query = """
    SELECT * WHERE {{
    ?c <{p}> ?x
    }}
    """.format(p=prefixmap[prefix])
    bindings = run_sparql(query)
    rows = [(r['c']['value'], r['x']['value']) for r in bindings]
    return rows

def map_id(id, prefix):
    m = fetchall_xrefs(prefix)
    if id in m:
        return m[id]
    else:
        return [id]
    

def fetchall_sp(s,p):
    """
    fetch all triples for a property
    """
    query = """
    SELECT * WHERE {{
    <{s}> <{p}> ?x
    }}
    """.format(s=s, p=prefixmap[p])
    bindings = run_sparql(query)
    rows = [r['x']['value'] for r in bindings]
    return rows

def canned_query(n,s):
    """
    uses canned query
    """
    qobj = qmap[n]
    chain = qobj['chain']
    prefix = qobj['prefix']
    whr = chain2where(chain + [prefix], 'x')
    query = """
    SELECT * WHERE {{
    <{s}> {w}
    }}
    """.format(s=s, w=whr)
    bindings = run_sparql(query)
    rows = [ensure_prefixed(r['x']['value'], prefix) for r in bindings]
    return rows


def chain2where(chain, v):
    [head] = chain[0:1]
    p = prefixmap[head]
    if len(chain) == 1:
        return "<{}> ?{}".format(p, v)
    else:
        tail = chain[1:]
        return "<{}> [ {} ]".format(p, chain2where(tail, v))

# TODO: move to factory
#def make_aset(
