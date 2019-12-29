===================================
Contributing a documentation change
===================================

*pydicom's* documentation consists of a series of `ReStructuredText
<https://thomas-cokelaer.info/tutorials/sphinx/rest_syntax.html>`_ file located
in the project's ``pydicom/doc`` directory which are converted to HTML using
`Sphinx <http://www.sphinx-doc.org>`_.

Changes to the documentation generally come in two forms:

* Improvements such as fixing typos and errors, adding better explanations and
  more examples
* Documentation of new features

This tutorial will take you through the process of:

* Downloading the current documentation
* Installing required libraries (if any)
* Creating a new git branch
* Making a change to the documentation
* Building and previewing your changes
* Committing the changes and making a pull request

Download the documentation
==========================

1. Sign up to `GitHub <https://github.com>`_ and
   `fork pydicom <https://github.com/pydicom/pydicom/fork>`_
2. Install `Git <https://git-scm.com/downloads>`_. If you're new to Git,
   the Django project has a good introduction on `working with Git and GitHub
   <https://docs.djangoproject.com/en/3.0/internals/contributing/writing-code/working-with-git/>`_.
   You can also take a look at the `GitHub branch-based workflow
   <https://guides.github.com/introduction/flow/>`_
3. Using the command line, ``cd`` to the directory where you want your
   local copy of *pydicom* to live. The source code can then be downloaded
   using::

     $ git clone https://github.com/YourUsername/pydicom.git

4. (Optional) We recommend that you install your development copy of *pydicom*
   in a virtual environment. See the :doc:`virtual environments<virtualenvs>`
   tutorial for more information.

   Create a new virtualenv ``pyd-doc``, using a Python 3.X version such
   as 3.7::

   $ mkvirtualenv -p /path/to/python3.7 pyd-doc

5. Install the cloned copy of *pydicom* (``-e`` for editable mode)::

   $ pip install -e pydicom/


Install required libraries
==========================

::

  $ pip install sphinx sphinx-rtd-theme sphinx-gallery


Create a new branch
===================
Create a new branch ``doc-tut`` for your changes (you can choose any name
that you want instead). Any changes made in this branch will be specific to
it and won't affect the main copy (the ``master`` branch) of
the documentation::

  $ git checkout -b doc-tut
