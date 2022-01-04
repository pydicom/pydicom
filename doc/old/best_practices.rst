.. _best_practices:
.. title:: Best Practices

Best Practices
==============

.. currentmodule:: pydicom

.. rubric:: Future-proof your code, and help ensure valid DICOM

Introduction
------------

There are some features of *pydicom* that allow you to help check your code
for more strict DICOM practices, and to future-proof against major 
*pydicom* version changes.

It is recommended that you turn on two features if you can: 
enforcement of valid DICOM, and a flag to enable "future" pydicom changes.

Enforcing Valid DICOM
---------------------

*pydicom* has configuration options to help enforce valid DICOM:
:attr:`~pydicom.config.settings.reading_validation_mode` and
:attr:`~pydicom.config.settings.writing_validation_mode`.
The first setting is about validation of values read from existing DICOM data,
the second about validation of newly created and written values.

Both can have the values `~pydicom.config.IGNORE`,
`~pydicom.config.WARN` and `~pydicom.config.RAISE`.

As the name suggests, some non-standard DICOM datasets may result in a warning
(this is the default for `reading_validation_mode`) or in a raised exception
(the default for `writing_validation_mode`). If `IGNORE` is set, the validation
is not performed in most cases. This setting may be used in some special
cases where you want to avoid the validation.

The setting for `writing_validation_mode` may be changed for some cases,
where writing invalid DICOM is needed to support some legacy software, but
this is generally not recommended.

The default setting for `reading_validation_mode` allows you to deal with files
that do not strictly adhere to the DICOM Standard. Setting it to
`RAISE` can help to ensure that only valid DICOM data is accepted.

These flags do not guarantee strict DICOM results, as not all of the possible
validations from the DICOM Standard are checked. Included are checks for
correct value length, contained character set and for predefined formats where
applicable (such as for date/time related values).

To change a flag in your code:

.. code-block:: python

  from pydicom import config
  config.settings.reading_validation_mode = config.RAISE

Note that you *must not* use 
:code:`from pydicom.config.settings import reading_validation_mode`.
That makes the `reading_validation_mode` variable local only to that module,
so *pydicom* would not see your change to its value.

Future-proofing your code
-------------------------

*pydicom*, like all software, must balance its evolution with not breaking
existing code using the library. Sometimes, major changes are necessary
to make significant improvements to the library.

To help you protect your code against future changes, *pydicom* allows you
to flag that it should behave as it will for any known upcoming 
major changes.

Running your code with this turned on will help identify any parts of 
your code that are not compatible with the known changes in the next major
version of *pydicom*.

The simplest way to set this behavior is to set an environment variable
``PYDICOM_FUTURE`` to "True". For example to temporarily turn it on in the
current terminal session:

.. code-block::
  
  SET PYDICOM_FUTURE=True           (Windows)

  export PYDICOM_FUTURE=True        (many linux environments)

If you wish to turn off the behavior, you can
either remove the environment variable, or set it to "False". See your
operating system documentation for more details on setting or removing
environment variables.

The other way to enable the future behavior is to turn it on at run-time
using the :func:`~pydicom.config.future_behavior` function:

.. code-block:: python

  from pydicom import config
  config.future_behavior()

If you needed to turn the future behavior off again at run-time, call
:func:`~pydicom.config.future_behavior` with False:

.. code-block:: python

  config.future_behavior(False)


Limiting the *pydicom* major version in your package
----------------------------------------------------

Another way to avoid breaking changes in future *pydicom* versions is to
limit the version of *pydicom* that your code uses.

If you follow standard Python packaging recommendations, you can add a line
to your `requirements.txt` file to limit the *pydicom* version to the current
major version.  E.g. a line like:

.. code-block::

  pydicom >=2.0,<3.0

in the `requirements.txt` file will ensure that those installing your package
will get the same major version (in the example, version 2) of *pydicom*
that you have developed the code for. This works best if your package is
installed in a virtual environment.