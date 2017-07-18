FROM ubuntu:16.04
RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y python-pip git
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y texlive texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended
RUN pip install --upgrade pip
RUN pip install Sphinx==1.4
RUN pip install sphinx_rtd_theme
RUN pip install alabaster 
RUN pip install sphinx_bootstrap_theme
WORKDIR /tmp
RUN git clone https://github.com/pydicom/pydicom
RUN git clone https://github.com/sphinx-gallery/sphinx-gallery
WORKDIR sphinx-gallery
RUN pip install -r requirements.txt
RUN python setup.py install
WORKDIR /tmp/pydicom
RUN python setup.py install
RUN pip install numpydoc
RUN mkdir /data
WORKDIR /data
CMD ["/bin/bash"]
