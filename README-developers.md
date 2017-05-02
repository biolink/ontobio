
## Release instructions

This section is only relevant for project maintainers.
To create a new release, do the following:

1. Bump the `__version__` in [`ontobio/__init__.py`](ontobio/__init__.py).

3. Run the following commands:
    
  ```sh
  TAG=v`python setup.py --version`
  git add ontobio/__init__.py
  git commit --message="Upgrade to $TAG"
  git push
  git tag --annotate $TAG --message="Upgrade to $TAG"
  git push --tags
  ```
