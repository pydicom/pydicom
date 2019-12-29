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
* Installing required libraries
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
   local copy of *pydicom* to live. The documentation can then be downloaded
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


Building and previewing
=======================

::

  $ cd pydicom/doc
  $ make html

::

  $ make clean && make html


Making a change to the documentation
====================================



Committing your changes and making a pull request
=================================================
To commit the changes::

  $ git commit

This will open a text editor so you can add the commit message. Alternatively,
if you only want a short commit message you can do::

  $ git commit -m "Add NewDefinedUID"

Which will commit with the message *"Add NewDefinedUID"*. After committing the
patch, send it to your fork::

  $ git push origin new-uid

You can create a pull request by visiting the `pydicom GitHub page
<https://github.com/pydicom/pydicom>`_ where you
should see your branch under *"Your recently push branches"*. Click *"Compare &
pull request"* and fill out the title (with a ``[WIP]`` prefix, i.e.
``[WIP] Add NewDefinedUID to uid.py``) and follow the  instructions in the
main entry window.

To submit the pull request (PR) for real - **please don't do this for
this example!** - then on the next page you would click *"Create pull
request"*.
Creating the PR will automatically start our checks; that the tests pass and
the test coverage is good, that the documentation builds OK, etc.

If all the checks pass and you're happy with your changes, change the PR title
prefix to ``[MRG]``. This indicates that you consider the PR ready to be
reviewed and merged into the main branch. You can also ask for a review or help
at any point after creating the PR.

What happens next?
==================
One or more reviewers will look at your pull-request and may make suggestions,
ask for clarification or request changes. Once the reviewers are happy then the
pull request will be approved and your changes will be merged into the
``master`` branch and become part of *pydicom*. Congratulations!
