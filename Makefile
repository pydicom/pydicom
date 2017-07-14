# simple makefile to simplify repetitive build env management tasks under posix

# caution: testing won't work on windows

test-code:
	py.test tests

test-doc:
	pytest  doc/*.rst

test-coverage:
	rm -rf coverage .coverage
	py.test tests --cov-report term-missing --cov=pydicom

test: test-code test-doc

doc:
	make -C doc html

clean:
	find . -name "*.so" -o -name "*.pyc" -o -name "*.md5" -o -name "*.pyd" -o -name "*~" | xargs rm -f
	find . -name "*.pyx" -exec ./tools/rm_pyx_c_file.sh {} \;
	rm -rf .cache
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf doc/auto_examples
	rm -rf doc/generated
	rm -rf doc/modules
	rm -rf examples/.ipynb_checkpoints

code-analysis:
	flake8 pydicom | grep -v __init__ | grep -v external
	pylint -E -i y pydicom/ -d E1103,E0611,E1101
