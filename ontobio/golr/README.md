# Python API for any golr instance (GO or Monarch)

Currently focuses on association models.

See golr_query.py for more documentation

## Association Modeling

### Association Results Object

For any associations query, a result object is returned. This may include the fields

 * associations - list of Association objects
 * compact_associations - list of Association object, in compact form
 * objects - list of all objects

### Compact Associations

One entry per subject (gene, disease, etc), objects are compacted as a list

```
{'relation': None,
 'subject': 'ZFIN:ZDB-GENE-050417-357',
 'objects': ['GO:0005488', 'GO:0009953', 'GO:0048731']}
```

note this model omits metadata such as evidence, etc    

### Associations

One entry per association


## Command Line

```
./biogolr/bin/qbiogolr.py -p subClassOf  -t tree -r hp -C phenotype query NCBIGene:84570 
```

```
./biogolr/bin/qbiogolr.py -p subClassOf  -t obo -r hp -C phenotype query NCBIGene:84570 
```

All diseases for an HPO class:

```
qbiogolr.py  -C disease HP:0006561
```

All genes for an HPO class, and draw hierarchy for results

```
qbiogolr.py -t tree -v -r hp  -C gene HP:0006561
```

as above, visualize gene-HPO graph:

```
qbiogolr.py -t png -d or -v -r hp  -C gene HP:0006561
```


Get zebrafish genes for a phenotype, map gene ids to ENSEMBL

```
qbiogolr.py -vv -M ENSEMBL -C gene GO:0030903PHENOTYPE
```
