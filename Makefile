all: serve

build:
	docker build -t test-api .

serve: build
	docker run -p 5420:8080 --rm -v $(shell pwd)/model/predictor.py:/opt/program/predictor.py test-model serve

test:
	./invoke_local.sh test.json
