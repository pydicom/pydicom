# Docs with Sphinx

## Building

This documentation will be automatically built and generated with continuous
 integration, via the [circle.yml](../.circleci/config.yml).

To get started, create a new virtualenv using Python 3:

```
mkvirtualenv -p /path/to/python3.X pydicom-sphinx
cd pydicom/
pip install -e .
pip install matplotlib
pip install sphinx sphinx_rtd_theme sphinx_gallery sphinx_copybutton sphinx_issues
cd doc
```

However, if you have need to test locally you may not want to use a virtualenv
or install dependencies. We have provided a
[Docker container](https://hub.docker.com/r/pydicom/pydicom-docs/) that will
let you do this.

To build the documentation run:

```
make html
```

Cleaning up the generated documentation files is sometimes necessary before
changes are apparent such as when new reStructuredText files are added, this
can be done with:

```
make clean
```

Whether you use the local approach or the Docker container, when you
finish you should then be able to cd into `_build/html` on your local machine
and preview with your browser of choice:

```
cd doc/_build/html
python -m http.server 9999
```

Then open your browser to [http://127.0.0.1:9999](http://127.0.0.1:9999)
