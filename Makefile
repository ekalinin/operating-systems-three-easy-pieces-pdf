all: book

env:
	virtualenv -p python3.8 env && \
		. env/bin/activate && \
		pip install -r requirements.txt

book: env
	. env/bin/activate && \
		python ostep.py

clear-env:
	rm -rf env
