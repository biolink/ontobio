#!/usr/bin/env python3

__author__ = 'nlw'

import argparse
import logging
import unittest
import json

import ontobio.obograph_util
from ontobio.cgraph import CompactGraph

def main():

    parser = argparse.ArgumentParser(description='SciGraph'
                                                 'Client lib for SciGraph',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('files',nargs='*')
    args = parser.parse_args()
    for fn in args.files:
        f = open(fn, 'r')
        gd = json.load(f)
        g = gd['graphs'][0]
        cg = CompactGraph(nodes=g['nodes'], edges=g['edges'])
        cg.serialize()
        
    
    


if __name__ == "__main__":
    main()
    
