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

One area of *pydicom* that is changing is how settings are used
to control behavior. Settings are key to two best practice recommendations:
enforcement of valid DICOM, and a "future" flag for your code to
behave as if it was running in the next *pydicom* major version.

Settings: Fine-tuning *pydicom* behavior
----------------------------

*pydicom* has changed the way it handles settings.  Settings have been
used, for example, to change how *pydicom* reacts to non-standard DICOM
files, or how it writes files.

In the past *pydicom* used global settings in the :mod:`~pydicom.config` module.
This is not thread-safe, so the maintainers have been moving
*pydicom* to better methods, while preserving backwards-compatibility.
This means that until *pydicom* v4.0, there will be several ways to handle
these settings, and you will still see all these in the documentation.

The correct method to use now is to create :class:`~pydicom.config.Settings`
instances, and pass those to functions like :func:`~pydicom.dcmread` and
:func:`~pydicom.dcmwrite`.

Some examples will be shown in the section below.

Also, you can turn on 'future behavior' to ensure your code
complies with the upcoming *pydicom* major version changes
(see section :ref:`pydicom_future`)


Enforcing Valid DICOM
---------------------

*pydicom* has settings to help enforce valid DICOM:
:attr:`~pydicom.config.Settings.reading_validation_mode` and
:attr:`~pydicom.config.Settings.writing_validation_mode`.
The first setting is about validation of values read from existing DICOM data,
the second about validation of newly created and written values.

Both can be set using the enum :attr:`~pydicom.config.ValidationMode`,
with values :attr:`~pydicom.config.ValidationMode.IGNORE`,
:attr:`~pydicom.config.ValidationMode.WARN`
and :attr:`~pydicom.config.ValidationMode.RAISE`.

As the name suggests, some non-standard DICOM datasets may result in a warning
(this is the default for ``reading_validation_mode``) or in a raised exception
(the default for ``writing_validation_mode``). If ``IGNORE`` is set, the validation
is not performed in most cases. This setting may be used in some special
cases where you want to avoid the validation.

In the following example, without the optional `settings`
argument, a UserWarning is issued.  With these `settings`,
an error is raised instead:

    >>> from pydicom.config import Settings, RAISE
    >>> from pydicom.data.data_manager import get_testdata_file
    >>> filename = get_testdata_file("emri_small_jpeg_2k_lossless_too_short.dcm")
    >>> no_invalid = Settings(reading_validation_mode=RAISE)
    >>> ds = dcmread(filename, settings=no_invalid)
    ...
    EOFError: End of file reached before delimiter (FFFE,E0DD) found

The setting for ``writing_validation_mode`` may be changed for some cases,
where writing invalid DICOM is needed to support some legacy software, but
this is generally not recommended.

The default setting for ``reading_validation_mode`` allows you to deal with files
that do not strictly adhere to the DICOM Standard. Setting it to
``RAISE`` can help to ensure that only valid DICOM data is accepted.

These flags do not guarantee strict DICOM results, as not all of the possible
validations from the DICOM Standard are checked. Included are checks for
correct value length, contained character set and for predefined formats where
applicable (such as for date/time related values).



.. _pydicom_future:

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
``PYDICOM_FUTURE`` to ``True``. For example to temporarily turn it on in the
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
to your ``requirements.txt`` or ``pyproject.toml`` file to limit the *pydicom*
version to the current major version.  E.g. a line like:

.. code-block::

  pydicom >=3.0,<4.0

in the ``requirements.txt`` file will ensure that those installing your package
will get the same major version (in the example, version 3) of *pydicom*
that you have developed the code for. This works best if your package is
installed in a virtual environment.
