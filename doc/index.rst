
:html_theme.sidebar_secondary.remove: true

=======
pydicom
=======

An easy to use Python package for creating, reading, modifying and writing
`DICOM <https://www.dicomstandard.org/>`_ files, with optional support for converting compressed
and uncompressed *Pixel Data* to `NumPy <https://www.numpy.org>`_
`ndarrays <https://numpy.org/doc/stable/reference/generated/numpy.ndarray.html>`_ (and back again).

..
    For the navigation links in the top bar, hidden to avoid clutter

.. toctree::
    :maxdepth: 1
    :hidden:

    guides/user/index
    tutorials/index
    guides/index
    auto_examples/index
    reference/index
    release_notes/index


Install
=======

.. tab-set::
    :class: sd-width-content-min

    .. tab-item:: pip

        .. code-block:: bash

            pip install pydicom

    .. tab-item:: conda

        .. code-block:: bash

            conda install -c conda-forge pydicom


For more detailed instructions, see the :doc:`installation guide<guides/user/installation>`.

Examples
========

.. tab-set::
    :class: sd-width-content-min

    .. tab-item:: Dataset I/O

        .. code-block:: python

            >>> from pydicom import dcmread
            >>> ds = dcmread("path/to/dataset")
            >>> ds.PatientName
            'CompressedSamples^CT1'
            >>> ds.PatientName = "Citizen^Jan"
            >>> print(ds)
            ...
            (0010,0010) Patient's Name                      PN: 'Citizen^Jan'
            (0010,0020) Patient ID                          LO: '4MR1'
            ...
            >>> ds.save_as("modified.dcm")

    .. tab-item:: DICOMDIR and File-sets

        .. code-block:: python

            >>> from pydicom import examples
            >>> from pydicom.fileset import FileSet
            >>> path = examples.get_path("dicomdir")  # Example DICOMDIR dataset
            >>> fs = FileSet(path)
            >>> fs.find_values("PatientID")
            ['77654033', '9890234']
            >>> ds = fs.find(PatientID='77654033')[0].load()
            >>> type(ds)
            <class 'pydicom.dataset.FileDataset'>
            >>> ds.PatientID
            '77654033'

    .. tab-item:: Convert pixel data to ndarray

        .. code-block:: python

            >>> from pydicom import dcmread, examples
            >>> path = examples.get_path("mr")  # Example MR dataset
            >>> ds = dcmread(path)
            >>> arr = ds.pixel_array  # requires NumPy, see the installation guide
            >>> arr
            array([[ 905, 1019, 1227, ...,  302,  304,  328],
               [ 628,  770,  907, ...,  298,  331,  355],
               [ 498,  566,  706, ...,  280,  285,  320],
               ...,
               [ 334,  400,  431, ..., 1094, 1068, 1083],
               [ 339,  377,  413, ..., 1318, 1346, 1336],
               [ 378,  374,  422, ..., 1369, 1129,  862]],
              shape=(64, 64), dtype=int16)

More usage examples can be found :doc:`here<auto_examples/index>`.

Documentation
=============

.. grid:: 1 1 2 2
    :gutter: 2 3 4 4

    .. grid-item-card::
        :img-top: _static/img/quick-start.svg
        :text-align: center

        **Quick start**
        ^^^

        If you're new to *pydicom*, start here for an introduction to our
        main features. Blah.

        +++

        .. button-ref:: tutorials/dataset_basics
            :expand:
            :color: primary
            :click-parent:

            Quick start

    .. grid-item-card::
        :img-top: _static/img/user-guide.svg
        :text-align: center

        **User guide**
        ^^^

        The user guide covers usage of *pydicom's* core classes and functions as
        well as explanations of the relevant parts of the DICOM Standard.

        +++

        .. button-ref:: guides/user/index
            :expand:
            :color: primary
            :click-parent:

            User guide

    .. grid-item-card::
        :img-top: _static/img/learning.svg
        :text-align: center
        :class-item: pydicom-learning

        **Learn**
        ^^^

        Our collection of tutorials and other usage guides.

        +++

        .. button-ref:: tutorials/index
            :color: primary

            Tutorials

        .. button-ref:: guides/index
            :color: primary

            Guides

    .. grid-item-card::
        :img-top: _static/img/api-reference.svg
        :text-align: center

        **API Reference**
        ^^^

        The API reference documentation contains detailed descriptions of the classes,
        functions, modules and other objects included in *pydicom*.

        +++

        .. button-ref:: reference/index
            :expand:
            :color: primary
            :click-parent:

            API reference
