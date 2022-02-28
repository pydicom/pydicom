=================================
Contributing a source code change
=================================

This tutorial will take you through the process of:

* Downloading the current source code
* Installing required libraries (if any)
* Running the test suite
* Creating a new git branch
* Making a change and documenting it
* Previewing your changes
* Committing the changes and making a pull request

Download the current source code
================================

1. Sign up to `GitHub <https://github.com>`_ and
   :gh:`fork pydicom <pydicom/fork>`
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
   in a virtual environment as this allows you to test different combinations
   of Python and installed packages. See the
   :doc:`virtual environments<virtualenvs>` tutorial for more information.

   Create a new virtualenv ``pydX.Y``, where ``X.Y`` is an installed Python
   version such as 3.7 and ``/path/to/pythonX.Y`` is the path to the
   corresponding Python executable::

   $ mkvirtualenv -p /path/to/pythonX.Y pydX.Y

5. Install the cloned copy of *pydicom* (``-e`` for editable mode)::

   $ pip install -e pydicom/


(Optional) Install required libraries
=====================================
If you're making changes to one of the pixel data handlers you'll need to
install `NumPy <https://numpy.org/>`_ as well as the library the handler is
based on.

For example, if you're working on the
:mod:`~pydicom.pixel_data_handlers.pillow_handler`
you'll also need to install `Pillow <https://pillow.readthedocs.io/>`_::

  $ pip install numpy pillow

See the :doc:`installation page<installation>` for details on installing
the optional libraries.


Install pytest and run the test suite
=====================================
When making changes to *pydicom* it's important that your changes don't
accidentally introduce bugs into other areas of the code. In order to
check that everything still works afterwards, you should run our test suite,
which is based on `pytest <https://docs.pytest.org/>`_.

Install and run pytest::

  $ pip install pytest
  $ cd pydicom/pydicom/tests
  $ pytest

While the tests are running you'll see a filename followed by a stream of
characters that represent the result of each test. A dot means the test
passed, **F** indicates a failure, **E** that an error occurred during
the test, **s** that the test was skipped (usually due to a missing
optional library) and **x** that the test failed as expected.

Once the tests are complete you should get a short summary of the results.
At this stage the entire test suite *should* pass. If you get any failures
or errors you should check the :gh:`issue tracker <pydicom/issues>` for any
relevant issues or create a new one if there are none.


Create a new branch
===================
Create a new branch ``new-uid`` for your changes (you can choose any name
that you want instead). Any changes made in this branch will be specific to
it and won't affect the main copy (the ``master`` branch) of the code::

  $ git checkout -b new-uid


Write tests for your changes
============================
If a change is to be accepted into *pydicom* it usually has to include tests.
For bug fixes you should write a regression test that reproduces the bug.
For new features you'll need to include tests that ensure the features
work as intended.

.. note::

   If you've never had to write tests before they can seem pretty daunting,
   especially if you're also learning how to use pytest from scratch. You may
   find the following resources useful:

   * Take a look at the
     :gh:`existing pydicom test suite <pydicom/tree/master/pydicom/tests>`
     and see how the tests are written. There are examples for writing
     :gh:`a single test <pydicom/blob/73cffe3151915b53a18b521656680d819e7e1a18/pydicom/tests/test_rle_pixel_data.py#L137>`,
     :gh:`a group of related tests <pydicom/blob/73cffe3151915b53a18b521656680d819e7e1a18/pydicom/tests/test_dataelem.py#L27>`,
     :gh:`testing for exceptions <pydicom/blob/73cffe3151915b53a18b521656680d819e7e1a18/pydicom/tests/test_handler_util.py#L834>`,
     :gh:`capturing log output <pydicom/blob/73cffe3151915b53a18b521656680d819e7e1a18/pydicom/tests/test_config.py#L28>`,
     :gh:`testing for warnings <pydicom/blob/73cffe3151915b53a18b521656680d819e7e1a18/pydicom/tests/test_pillow_pixel_data.py#L452>`,
     and running
     :gh:`parametrized tests <pydicom/blob/73cffe3151915b53a18b521656680d819e7e1a18/pydicom/tests/test_rle_pixel_data.py#L215>`.
   * Dive Into Python has a very nice `section on unit testing
     <https://diveinto.org/python3/unit-testing.html>`_ (however it uses
     ``unittest`` instead of pytest).
   * The `pytest documentation <https://docs.pytest.org/en/latest/example/index.html>`_
     may also be helpful

   If you're still having trouble writing a test for something, once
   you've created a pull request (to be discussed a bit later) add a comment
   asking for help.

Let's say we wanted to add a new `pre-defined UID
<https://pydicom.github.io/pydicom/dev/reference/uid.html#predefined-uids>`_
to *pydicom* with a value of ``1.2.3.4.500``. We'd first add a new test at the
bottom of :gh:`test_uid.py <pydicom/blob/master/pydicom/tests/test_uid.py>`::

  def test_new_uid():
      """Test uid.NewDefinedUID."""
      from pydicom.uid import NewDefinedUID
      assert '1.2.3.4.500' == NewDefinedUID

Since we haven't made any modification to the actual source code, when we
run the tests we should get a failure::

  $ pytest test_uid.py

::

      def test_new_uid():
          """Test uid.NewDefinedUID."""
  >       from pydicom.uid import NewDefinedUID
  E       ImportError: cannot import name 'NewDefinedUID'

  test_uid.py:380: ImportError

If all the tests passed then make sure you've added the test to the correct
file and that the test itself is written correctly.


Make a code change and document it
==================================
Next we'll make changes to the actual source code. Open
:gh:`uid.py <pydicom/blob/master/pydicom/uid.py>` in a text editor and around
:gh:`line 236 <pydicom/blob/73cffe3151915b53a18b521656680d819e7e1a18/pydicom/uid.py#L236>`
make the following changes::

  RLELossless = UID('1.2.840.10008.1.2.5')
  """1.2.840.10008.1.2.5"""
  # **Add this**
  NewDefinedUID = UID('1.2.3.4.500')
  """1.2.3.4.500"""

The line ``"""1.2.3.4.500"""`` is the `docstring
<https://www.python.org/dev/peps/pep-0257/>`_ for our new UID. In order for
it to be included in the API reference documentation we'll also need to update
:gh:`uid.rst <pydicom/blob/master/doc/reference/uid.rst>`::

  JPEG2000MultiComponentLossless
  JPEG2000MultiComponent
  RLELossless
  NewDefinedUID

When making changes, and especially when adding new features, it's important
that they're documented. It's very difficult for users to find and
understand how to use code that hasn't been documented, or whose documentation
contains errors. For more information on how to properly document *pydicom*
see :doc:`writing documentation</guides/writing_documentation>`.

Now we run the tests again so we can see whether or not the code we added is
working::

  $ pytest test_uid.py

Everything should pass. If it doesn't, make sure you've correctly added the
new UID. Once you're happy that the tests in ``test_uid.py`` are working you
should make sure the entire test suite passes::

  $ pytest


Preview your changes
====================
It's a good idea to go through all the changes you've made by first staging
and then displaying the difference between the current copy and the initial
version we first checked out with::

  $ git add --all
  $ git diff --cached

You can scroll through the output using the up and down keys and quit with
**q**. Lines with a **-** in front will be removed and lines with a **+**
added. If everything looks good then it's time to commit the changes.


Commit your changes and make a pull request
===========================================
To commit the changes::

  $ git commit

This will open a text editor so you can add the commit message. Alternatively,
if you only want a short commit message you can do::

  $ git commit -m "Add NewDefinedUID"

Which will commit with the message *"Add NewDefinedUID"*. After committing the
patch, send it to your fork::

  $ git push origin new-uid

You can create a pull request by visiting the :gh:`pydicom GitHub page
<pydicom>` where you should see your branch under *"Your recently push
branches"*. Click *"Compare & pull request"* and fill out the title (with a
``[WIP]`` prefix, i.e. ``[WIP] Add NewDefinedUID to uid.py``) and follow the
instructions in the main entry window.

To submit the pull request (PR) for real - **please don't do this for
this example!** - then on the next page you would click *"Create pull
request"*.
Creating the PR would automatically start our checks; that the tests pass and
the test coverage is good, that the documentation builds OK, etc.

If all the checks passed and you were happy with your changes, you'd change
the PR title prefix to ``[MRG]``. This would indicate that you considered the
PR ready to be reviewed and merged into the main branch. You could also ask
for a review or help at any point after creating the PR.

What happens next?
==================
One or more reviewers would look at your pull request and may make suggestions,
ask for clarification or request changes. Once the reviewers were happy,
the pull request would be approved and your changes merged into the
``master`` branch where they would become part of *pydicom*.

However, because this is just an example, all we're going to do is clean up the
changes we've made. First we switch back to the ``master`` branch::

  $ git checkout master

We delete the local copy of the branch we created::

  $ git branch -d new-uid

And lastly we delete the remote copy on GitHub. Go to
``https://github.com/YourUsername/pydicom/branches``, find the ``new-uid``
branch and click the corresponding red bin icon. All done!
