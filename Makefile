GITVERSIONFILE = mwlib/rl/_gitversion.py

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
	echo gitversion=\"$(shell git describe --tags)\" >$(GITVERSIONFILE)
	echo gitid=\"$(shell git rev-parse HEAD)\" >>$(GITVERSIONFILE)
	python setup.py build sdist
	rm -f $(GITVERSIONFILE)*

clean::
	git clean -xfd

easy-install:: clean sdist
	easy_install dist/*

pip-install:: clean sdist
	pip install dist/*
