.PHONY: test upload clean bootstrap

test:
	_virtualenv/bin/pyflakes graphjoiner tests
	sh -c '. _virtualenv/bin/activate; pytest tests'

test-all:
	tox

upload: test-all
	python setup.py sdist bdist_wheel upload
	make clean
	
register:
	python setup.py register

clean:
	rm -f MANIFEST
	rm -rf dist build
	
bootstrap: _virtualenv
	_virtualenv/bin/pip install -e .
ifneq ($(wildcard test-requirements.txt),) 
	_virtualenv/bin/pip install -r test-requirements.txt
endif
	make clean

_virtualenv: 
	virtualenv _virtualenv
	_virtualenv/bin/pip install --upgrade pip
	_virtualenv/bin/pip install --upgrade setuptools
