
## Release instructions

* Note: pandoc must be installed before this works. You can install with
brew or apt-get or yum.

This section is only relevant for project maintainers.
To create a new release, do the following:

1. First check whether the `__version__` in [`ontobio/__init__.py`](ontobio/__init__.py) matches with the latest tag or PyPI release. If the version is the same then you need to bump the version to make a new release. Follow semantic versioning guidelines to decide whether the bump in version is major or minor.

2. If you did bump the version then run the following commands:

```sh
TAG=v`python setup.py --version`
git add ontobio/__init__.py
git commit --message="Upgrade to $TAG"
git push
git tag --annotate $TAG --message="Upgrade to $TAG"
git push --tags
  ```


3. Releasing on PyPI

> To ensure this is successful, make sure you have relevant permissions to Ontobio package on [PyPI](https://pypi.org/project/ontobio/)

Run the following commands:

```sh
make cleandist
python setup.py sdist bdist_wheel bdist_egg
twine upload --repository-url https://upload.pypi.org/legacy/ --username PYPI_USERNAME dist/*
```

