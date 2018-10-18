# DOCS
# See https://github.com/pypa/virtualenv/issues/149
pydoc-%:
	python -m pydoc ontobio.ontol

#PACKAGES = prefixcommons scigraph biogolr
PACKAGES = ontobio prefixcommons
subpackage_tests: $(patsubst %,test-%,$(PACKAGES))

test:
	pytest tests/*.py tests/unit/

debug_test:
	pytest --log-cli-level DEBUG -s tests/*.py

t-%:
	pytest --log-cli-level INFO -s tests/test_$*.py

foo:
	which pytest

# only run local tests
travis_test:
	pytest tests/test_*local*.py tests/test_*parser*.py tests/test_qc.py tests/unit/

cleandist:
	rm dist/* || true

# TODO: manually increment version in ontobio/__init__.sh, run . bump.sh, then this
release: cleandist
	python setup.py sdist bdist_wheel bdist_egg
	twine upload dist/*

nb:
	PYTHONPATH=.. jupyter notebook

# Hack: generate marshmallow schema from flaskrest serializers
# used to make assoc_schema.py
mm:
	./bin/flask2marshmallow.pl ../biolink-api/biolink/datamodel/serializers.py


# Building docker image
VERSION = "v0.0.1" 
IM=cmungall/ontobio

docker-build:
	@docker build -t $(IM):$(VERSION) . \
	&& docker tag $(IM):$(VERSION) $(IM):latest

docker-run:
	docker run --rm -ti --name ontobio $(IM)

docker-run-notebook:
	docker run -p 8888:8888 --rm -ti --name ontobio $(IM) PYTHONPATH=.. jupyter notebook --ip 0.0.0.0 --no-browser

docker-clean:
	docker kill $(IM) || echo not running ;
	docker rm $(IM) || echo not made 

docker-publish: docker-build
	@docker push $(IM):$(VERSION) \
	&& docker push $(IM):latest
