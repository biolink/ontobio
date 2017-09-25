CHANGES
=======

0.2.19
------

* gaf parsing: reject expressions in extensions field that have bad IDs, fixes #99
* lexical mapping: improved handling of xrefs

0.2.18
------

* lexmap output now excludes index column
* allow custom synsets for lexmap
* fixed bug whereby bulk golr fetch not iterated

0.2.17
------

* Fixed bug where CHEBI xref labels were treated as class labels
* Various lexical mapping improvements #97 #95

0.2.16
------

* Added ability to parse skos
* Added more detailed scoring and documentation for lexical  mapping.
* lexmap fixes: Fixed #93, #94

0.2.15
------

* lexical mappings #88 #89
* set ontology id when retrieving from JSON or SPARQL

0.2.11
------

* #63, added rdf generation
* #62, python version check, @diekhans
* using rst for README
* #56 , assocmodel now allows retrieval of full association objects
* Added GPI writer

0.2.10
------

* Fixed bug with handling of replaced_by fields in obsolete nodes, #51

0.2.9
-----

* Turned down logging from info to warn for skipped lines

0.2.7
-----

* gaf parsing is more robust to gaf errors
* bugfix function call parameter ordering

0.2.6
-----

* Implementing paging start parameters. For https://github.com/biolink/biolink-api/issues/60

0.2.5
-----

* bugfix for processing gaf lines that do not have the right number of columns

0.2.4
-----

* added ecomap.py
* fixes for planteome
