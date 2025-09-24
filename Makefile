deps:
	pip3.10 install -r requirements.txt

run:
	python3.10 src/main.py

push:
	git push origin main
