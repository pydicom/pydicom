# Docs with Sphinx

This documentation will be automatically built and generated with continuous
 integration, via the [circle.yml](../.circleci/config.yml). You can also
 generate them locally by installing dependencies (you may need the below):

```
pip install sphinx
pip install sphinx_rtd_theme
```

and then to generate:

```
cd pydicom/doc
make html
```

However, if you have need to test locally, you may not want to install dependencies. We have provided a [Docker container](https://hub.docker.com/r/pydicom/pydicom-docs/) that will let you do this.

Whether you use the above local approach or the Docker container, when you finish you should then be able to cd into `_build/html` on your local machine and preview with your webserver of choice

```
cd doc/_build/html
python -m http.server 9999
```

Then open your browser to [http://127.0.0.1:9999](http://127.0.0.1:9999)
