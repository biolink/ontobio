See [command line docs](http://ontobio.readthedocs.io/en/latest/commandline.html#commandline) on ReadTheDocs

To test validate.py "validate" command, the command that produces the final GPADs in the pipeline via the "mega make" 
(aka: "produces GAFs, GPADs, ttl" stage), on a particular source:

```bash
poetry install
poetry run validate produce -m ../go-site/metadata --gpad -t . -o go-basic.json --base-download-url "http://skyhook.berkeleybop.org/[PIPELINE_BRANCH_NAME]/" --only-dataset mgi MGI
poetry run validate produce -m ../go-site/metadata --gpad -t . -o go-basic.json --base-download-url "http://skyhook.berkeleybop.org/[PIPELINE_BRANCH_NAME]/" --only-dataset goa_chicken goa
```


To test whether a GAF file is valid (passes all the GORules):
```bash
poetry install
poetry run python3 ontobio-parse-assocs.py --file [path_to_file.gaf] --format GAF -o mgi_valid.gaf --report-md mgi.report.md -r [path_to_go.json] -l all validate
```