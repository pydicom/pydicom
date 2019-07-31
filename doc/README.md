# Docs with Sphinx

## Building

This documentation will be automatically built and generated with continuous
 integration, via the [circle.yml](../.circleci/config.yml).

To get started, create a new virtualenv using Python 3:

```
mkvirtualenv -p /path/to/python3.X pydicom-sphinx
cd pydicom/
pip install -e .
pip install sphinx sphinx_rtd_theme sphinx_gallery
cd doc
```

However, if you have need to test locally you may not want to use a virtualenv
or install dependencies. We have provided a [Docker container](https://hub.docker.com/r/pydicom/pydicom-docs/) that will let you
do this.

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
and preview with your webserver of choice:

```
cd doc/_build/html
python -m http.server 9999
```

Then open your browser to [http://127.0.0.1:9999](http://127.0.0.1:9999)


## Non-API Style Guide

Recommended variable names:

`ds` for a Dataset() or FileDataset()
`elem` for a DataElement()
`arr` for a numpy array

Examples of internal references to the API
:class:`Dataset<pydicom.dataset.Dataset>`
:func:`Dataset.pixel_array<pydicom.dataset.Dataset.pixel_array>`

Examples of external references to third-party API
:class:`str()<str>`
:class:`ndarray<numpy.ndarray>`

Mentions of *pydicom* objects should be an internal reference to the API,
similarly mentions of Python or third-party objects should be an external
reference to the corresponding docs.

Do:

A :class:`Dataset<pydicom.dataset.Dataset>` is similar to a Python
:class:`dict` whose keys are :class:`BaseTag<pydicom.tag.BaseTag>` objects and
values are :class:`DataElement<pydicom.dataelem.DataElement>` objects. The
:class:`DataElements<pydicom.dataelem.DataElement>` in the
:class:`Dataset<pydicom.dataset.Dataset>` can be iterated through using
``iter(Dataset)`` or by calling
:class:`Dataset.iterall()<pydicom.dataset.Dataset.iterall>`

Don't:

A :class:`Dataset<pydicom.dataset.Dataset>` is similar to a Python
:class:`dict` whose keys are :class:`BaseTag<pydicom.tag.BaseTag>` objects and
values are :class:`DataElement<pydicom.dataelem.DataElement>` objects. The
DataElements in the Dataset can be iterated through using ``iter(Dataset)`` or
by calling :class:`Dataset.iterall()<pydicom.dataset.Dataset.iterall>`


Short code should use the double-apostrophe markup:

If ``True`` then the value is determined from ``a + b = c``.

Elements should follow the style (gggg,eeee) *Name of Element* 

Tags should follow the DICOM convention of (gggg,eeee), i.e. as (0010,0020)
not as (0010, 0020)


## API Style Guide

When parameter names are mentioned within a docstring use `var_name`.

Short code should use the double-apostrophe markup:

If ``True`` then the value is determined from ``a + b = c``.

Elements should follow the style (gggg,eeee) *Name of Element*

Tags should follow the DICOM convention of (gggg,eeee), i.e. as (0010,0020)
not as (0010, 0020)
