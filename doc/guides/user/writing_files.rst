.. _writing_dicom_files:

Creating new datasets
=====================

.. currentmodule:: pydicom

Probably the most common use of *pydicom* is to read an existing DICOM file,
alter some elements, and write it back out again. The :doc:`Dataset basics tutorial
</tutorials/dataset_basics>` shows how to do this.

If you need to create a new DICOM dataset then you can either:

* Use the ``codify`` command-line utility to create Python code from an existing dataset.
* Create a new :class:`~pydicom.dataset.Dataset` instance and populate it.

.. warning::

  To be truly DICOM compliant, certain data elements will be required in the
  file meta information and in the main dataset. Also, you should create your
  own UIDs, implementation name, and so on.


.. _writing_files_using_codify:

Using ``codify``
----------------

*pydicom* has a command-line utility called ``codify`` that can produce Python code
that can be run to produce a copy of an existing DICOM file.

In other words: *pydicom* has a tool that can automatically generate
well-designed Python code for you - code that creates DICOM files. The only
requirement is that you have an existing DICOM file that looks approximately
like the one you need. You can then use that code as a model to work from. The
tool is especially useful with sequences, which can be tricky to code
correctly.

.. warning::

   The code produced by ``codify`` will contain all the information in the original
   file, which may include private health information or other sensitive
   information.  If the code is run, the resulting DICOM file will also contain
   that information. You may want to consider using de-identified DICOM files
   with ``codify``, or handling the output files according to your requirements for
   sensitive information.

One issue to be aware of is that ``codify`` will not create code for large items
like pixel data. Instead it creates a line like:

.. code-block:: python

   ds.PixelData = # XXX Array of 524288 bytes excluded

In that case, the code will produce a syntax error when run, and you will have
to edit the code to supply a valid value.

.. note::

   The ``--exclude-size parameter`` can set the maximum size of the data
   element value that is coded. Data elements bigger than that will have the
   syntax error line as shown above.

One potential disadvantage of ``codify`` is that it does not create loops.
If you have, say, 30 items in a Sequence, ``codify`` will produce code that
makes them one at a time. Code you wrote by hand would
likely create them in a loop, because most of the code needed is quite
repetitive. If you want to switch to a loop, you could use the first item's
code as a starting point, and modify as needed, deleting the code for the
other individual items.

For more information on the ``codify`` command, see the :doc:`codify</guides/cli/cli_codify>`
documentation.

``codify`` could also be called from code, rather than from a command line; you
can look at the :gh:`codify source code<pydicom/blob/main/src/pydicom/util/codify.py>` and the
``code_file`` function for a starting point.


Writing a file from scratch
---------------------------

The ``codify`` tool, described in the previous section, is a good starting point
for *pydicom* code, but if you can't (or don't want to) use that tool, then you
can certainly write code from scratch to make a complete DICOM file using
*pydicom*.

It's not particularly difficult, but to produce a valid DICOM file requires
specific items to be created.  A basic example of that is available in the
example file :ref:`sphx_glr_auto_examples_input_output_plot_write_dicom.py`.

Just don't forget the warnings in the sections above, and be sure
to create all the required DICOM data elements.
