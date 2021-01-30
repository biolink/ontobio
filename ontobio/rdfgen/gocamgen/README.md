## Translating GPAD to GO-CAM models with `gocamgen`
```
bin/validate.py -v gpad2gocams --gpad_path gpad2.0.zfin --gpi_path zfin.gpi2 --target target/zfin_models/ --ontology go.json --ontology ro.json --ttl
```
The args:
* `-v gpad2gocams` (the specific command within `validate.py`; this does what it sounds like it will do)
* `--gpad_path` and `--gpi_path` (paths to source GPAD and GPI files)
* `--target` (destination folder for model files)
* `--ontology go.json` and `--ontology ro.json` (these are the two ontology files we need, for now)
* `--ttl` (output to TTL format; omit this flag to output all models to a single [N-Quads](https://en.wikipedia.org/wiki/N-Triples#N-Quads) `.nq` file)

For `--ontology`, any format accepted by ontobio's ontology parsers is acceptable here. I used JSON 
([obographs](http://https//github.com/geneontology/obographs) standard) files since this will be the 
format they are in when the cmd is run within the GO pipeline. It also gets around ontobio calling 
out to owltools to process the ontology files.

To get `go.json` and `ro.json`, download [go.owl](http://purl.obolibrary.org/obo/go.owl) and 
[ro.owl](http://purl.obolibrary.org/obo/ro.owl) and convert them to JSON using the 
[robot](http://robot.obolibrary.org/) tool. For example:
```
robot convert -i go.owl -o go.json
```
After all of this, you should get a bunch of `.ttl` files to load into a [Noctua](https://github.com/geneontology/noctua) stack.