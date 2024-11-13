See [command line docs](http://ontobio.readthedocs.io/en/latest/commandline.html#commandline) on ReadTheDocs

To test validate.py "validate" command, the command that produces the final GPADs in the pipeline via the "mega make" 
(aka: "produces GAFs, GPADs, ttl" stage), on a particular source, run:
```bash
make test_travis_full
```

This makefile target will run the full validate.produce command using goa_cow, mgi, zfin, and goa_chicken sources,
producing GPAD, GAF files in the groups subdirectory and then do a check of the content of these products.  These
tests only run manually, not via CI because they take minutes to run.

alternatively, you can run the following commands to test the validate.produce command on a particular source, locally:

```bash
Note: snapshot below in the URL can be changed to any pipeline branch; its listed here for ease of cp/paste.
```bash
poetry install
poetry run validate produce -m ../go-site/metadata --gpad -t . -o go-basic.json --base-download-url "http://snapshot.geneontology.org/" --only-dataset mgi MGI --gpad-gpi-output-version 2.0
poetry run validate produce -m ../go-site/metadata --gpad -t . -o go-basic.json --base-download-url "http://snapshot.geneontology.org/" --only-dataset goa_chicken goa --gpad-gpi-output-version 2.0
poetry run validate produce -m ../go-site/metadata --gpad -t . -o go-basic.json --base-download-url "http://snapshot.geneontology..org/" --only-dataset zfin ZFIN --gpad-gpi-output-version 2.0
```

To test whether a GAF file is valid (passes all the GORules):
```bash
poetry install
poetry run python3 ontobio-parse-assocs.py --file [path_to_file.gaf] --format GAF -o mgi_valid.gaf --report-md mgi.report.md -r [path_to_go.json] -l all validate
```