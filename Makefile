# simple makefile to simplify repetitive build env management tasks under posix

# caution: testing won't work on windows

test-code:
	py.test --pyargs pydicom

test-doc:
	pytest --pyargs doc/*.rst

test-coverage:
	rm -rf coverage .coverage
	py.test --pyargs pydicom --cov-report term-missing --cov=pydicom

test: test-code test-doc

doc:
	make -C doc html

doc-noplot:
	make -C doc html-noplot

code-analysis:
	flake8 pydicom | grep -v __init__ | grep -v external
	pylint -E -i y pydicom/ -d E1103,E0611,E1101
