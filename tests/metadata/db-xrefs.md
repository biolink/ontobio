# go-dbxrefs

This is the source file for the GO prefix registry.

## Source

The source file is in YAML and is available here:

https://github.com/geneontology/go-site/blob/master/metadata/db-xrefs.yaml

## Browsing

The registry can be browsed here: http://amigo.geneontology.org/xrefs

## Schema

The schema is defined using kwalify, and is available here:

https://github.com/geneontology/go-site/blob/master/metadata/db-xrefs.schema.yaml

## Relationship to legacy format

We also support the [legacy xrf abbs format](http://geneontology.org/doc/GO.xrf_abbs_spec). A jenkins job writes to the [legacy GO.xrf_abbs](http://www.geneontology.org/doc/GO.xrf_abbs) file.

We recommend use of the yaml in all new applications.

## Contributions

To provide suggested edits, please click the [edit button](https://github.com/geneontology/go-site/edit/master/metadata/db-xrefs.yaml) on the source file. Select "create a branch and make a pull request". Name your branch according to your proposed change, e.g. `new-resource-FooBase` or `fix-metadata-for-FooBase`

Note you will need a github account.
