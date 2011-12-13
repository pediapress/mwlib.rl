GITVERSIONFILE = mwlib/rl/_gitversion.py
RST2HTML ?= rst2html.py

all:: messages README.html MANIFEST.in

messages::
	./compile_messages.py all

MANIFEST.in::
	./make_manifest.py

README.html: README.rst
	$(RST2HTML) README.rst >README.html

develop:: all
	python setup.py develop

sdist:: all
	@echo gitversion=\"$(shell git describe --tags)\" >$(GITVERSIONFILE)
	@echo gitid=\"$(shell git rev-parse HEAD)\" >>$(GITVERSIONFILE)
	@python setup.py -q build sdist 
	@rm -f $(GITVERSIONFILE)*

clean::
	git clean -xfd

pip-install:: clean sdist
	pip uninstall -y mwlib.rl || true
	pip install dist/*

update::
	git pull
	make pip-install
