all:: messages README.html MANIFEST.in

messages::
	./compile_messages.py

MANIFEST.in::
	./make_manifest.py

README.html: README.txt
	rst2html.py README.txt >README.html

develop:: all
	python setup.py develop

sdist:: all
	python setup.py -q build sdist

sdist-upload:: all
	python setup.py build sdist upload

egg:: all
	python setup.py bdist_egg

