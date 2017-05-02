# Initial Setup

```
export PATH $HOME/repos/ontobio/ontobio/bin
ogr -h
```

Note you need to be connected to a network

Note: command line interface may change

# Ontologies

The `ogr` command handles ontologies

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

# Associations

The `ogr-assoc` command handles ontologies


Examples:

```
ogr-assoc -v -r go -T NCBITaxon:9606 -C gene function enrichment -q GO:1903010 

ogr-assoc -v -r go -T NCBITaxon:10090 -C gene function dendrogram GO:0003700 GO:0005215 GO:0005634 GO:0005737 GO:0005739 GO:0005694 GO:0005730  GO:0000228 GO:0000262 

ogr-assoc -v -r go -T NCBITaxon:10090 -C gene function simmatrix MGI:1890081 MGI:97487 MGI:106593 MGI:97250 MGI:2151057 MGI:1347473

ogr-assoc -C gene function -T pombe -r go -f tests/resources/truncated-pombase.gaf query -q GO:0005622
```
