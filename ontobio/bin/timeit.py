#!/usr/bin/env python3

from ontobio.sparql2ontology import *
from networkx.algorithms.dag import ancestors
import time


def r():
    t1 = time.process_time()
    get_edges('pato')
    t2 = time.process_time()
    print(t2-t1)

r()
r()
r()

"""

LRU is much faster, but does not persist. However, should be fast enough

# percache

## ENVO

$ python ./obographs/bin/timeit.py 
QUERYING:envo
1.103934
0.0032450000000001644
0.003185999999999911

$ python ./obographs/bin/timeit.py 
0.018115000000000048
0.00362800000000002
0.003180000000000016

## GO

$ python ./obographs/bin/timeit.py 
QUERYING:go
13.218031
0.04876699999999978
0.04904600000000059

$ python ./obographs/bin/timeit.py 
0.05928599999999995
0.045568
0.045347000000000026

# lru

$ python ./obographs/bin/timeit.py 
QUERYING:envo
1.0635080000000001
2.0000000000575113e-06
1.000000000139778e-06

$ python ./obographs/bin/timeit.py 
QUERYING:go
13.225105000000001
2.000000000279556e-06
0.0


"""
