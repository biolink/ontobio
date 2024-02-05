See [command line docs](http://ontobio.readthedocs.io/en/latest/commandline.html#commandline) on ReadTheDocs

To test validate.py on a particular source:
```bash
poetry install
poetry run validate produce -m ../go-site/metadata --gpad -t /Users/Smoxon/Documents/src/ontobio -o go-basic.json --only-dataset mgi MGI
poetry run validate produce -m ../go-site/metadata --gpad -t /Users/Smoxon/Documents/src/ontobio -o go-basic.json --only-dataset goa_chicken goa
```
