all: serve

build:
	docker build -t test-api .

serve: build
	docker run -p 5420:5420 --rm -v $(shell pwd)/model/predictor.py:/opt/program/predictor.py test-api serve

test:
	./invoke_local.sh test.json

