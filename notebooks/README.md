## Viewing

For optimal viewing, browse this folder [using nbviewer](http://nbviewer.jupyter.org/github/biolink/ontobio/tree/master/notebooks/) .

See [notebooks section](http://ontobio.readthedocs.io/en/latest/notebooks.html) on ReadTheDocs

## Dynamic Execution / Editing

First:

```
pyvenv venv
source venv/bin/activate
export PYTHONPATH=.:$PYTHONPATH
pip install -r requirements.txt
pip install jupyter
```

To run a notebook, do the following from the parent folder:

```
make nb
```

Then browse to the 'notebooks' fold
