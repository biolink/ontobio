[![Build Status](https://travis-ci.org/biolink/ontobio.svg?branch=master)](https://travis-ci.org/biolink/ontobio)
[![DOI](https://zenodo.org/badge/13996/biolink/ontobio.svg)](https://zenodo.org/badge/latestdoi/13996/biolink/ontobio)

# ontobio - a python API for working with ontology graphs

This module provides objects and utility methods for working with
ontologies and associations of entities (genes, variants, etc) to
ontology classes.

The ontologies and associations can either be local files or provided
by remote services (currently the OntoBee SPARQL service for
ontologies and a Monarch or GO Golr service for associations).

# API Docs

[ontobio](https://www.pydoc.io/pypi/ontobio-0.1.2/index.html) on pydoc.io

# Ontologies

There are two ways of initiating an ontology object:

 * via a local obo-json file
 * via remote connections to OBO PURLs
 * via remote query to a SPARQL service (currently  ontobee, but soon others)

Persistent caching is used (currently cachier) to avoid repeated expensive I/O connections

This is handled via the [ontol_manager.py](ontobio/ontol_manager.py)
module. This creates an ontology object (see [ontol.py](ontobio/ontol.py) ).

Note that object modeling is lightweight - we use the python networkx
package for representing the basic graph portion of an ontology. See
also the [obographs](https://github.com/geneontology/obographs) spec.

# Associations

See the ontobio.golr backage

# Command Line Usage

## Initial Setup

```
export PATH $HOME/repos/bioink-api/ontobio/bin
ogr -h
```

Note you need to be connected to a network

Note: command line interface may change

## Connecting to ontologies

Specify an ontology with the `-r` option. this will always be the OBO name, for example `go`, `cl`, `mp`, etc

 * `-r go` connect to GO via default method (currently SPARQL)
 * `-r obo:go` connect to GO via download and cache of ontology from PURL
 * `-r /users/my/my-ontologies/go.json` use local download of ontology

In the following we assume default method, but can be substituted.

## Ancestors queries

List all ancestors:

```
ogr -r cl neuron
```

Show ancestors as tree, following only subclass:

```
ogr -r cl -p subClassOf -t tree neuron
```

generates:

```
     % GO:0005623 ! cell
      % CL:0000003 ! native cell
       % CL:0000255 ! eukaryotic cell
        % CL:0000548 ! animal cell
         % CL:0002319 ! neural cell
          % CL:0000540 ! neuron * 
       % CL:0002371 ! somatic cell
        % CL:0002319 ! neural cell
         % CL:0000540 ! neuron * 
```

Descendants of neuron, parts and subtypes

```
ogr -r cl -p subClassOf -p BFO:0000050 -t tree -d d neuron
```

Descendants and ancestors of neuron, parts and subtypes

```
ogr -r cl -p subClassOf -p BFO:0000050 -t tree -d du neuron
```

All ancestors of all classes 2 levels down from subclass-roots within CL:

```
ogr -r cl -P CL -p subClassOf -t tree -d u -L 2
```

## Visualization using obographviz

Requires: https://www.npmjs.com/package/obographviz

Add og2dot.js to path

```
ogr -p subClassOf BFO:0000050 -r go -t png   a nucleus
```

This proceeds by:

 1. Using the python ontobio library to extract a networkx subgraph around the specified node
 2. Write as obographs-json
 3. Calls og2dot.js

Output:

![img](https://github.com/biolink/biolink-api/raw/master/ontobio/docs/nucleus.png)

## Search

List exact matches to neuron

```
ogr -r cl neuron
```

Terms starting with neuron, SQL style

```
ogr -r cl neuron%
```

Terms starting with neuron, regex (equivalent to above)

```
ogr -r cl -s r ^neuron
```

Terms ending with neuron

```
ogr -r cl -s r neuron$
```

Terms containing the string neuron

```
ogr -r cl -s r neuron
```

Note: any of the above can be fed into other renderers, e.g. trees, graphs

E.g. terms containing neuron, to obo

```
ogr -r cl %neuron% -t obo
```

E.g. terms ending neuron, to tree

```
ogr -r cl %neuron -t tree
```

## Release instructions

This section is only relevant for project maintainers.
To create a new release, do the following:

1. Bump the `__version__` in [`ontobio/__init__.py`](ontobio/__init__.py).

3. Run the following commands:
    
  ```sh
  TAG=v`python setup.py --version`
  git add ontobio/__init__.py
  git commit --message="Upgrade to $TAG"
  git push
  git tag --annotate $TAG --message="Upgrade to $TAG"
  git push --tags
  ```
