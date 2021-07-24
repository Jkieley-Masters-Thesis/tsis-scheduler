REPOSITORY?=jkieley/tsis-scheduler
TAGNAME?=latest

# Ensure that the python version on the PATH is version 3.7.6
# You can check this by useing the version check  task

# Builds the docker image
build:
	docker build --add-host=jamesk-kubernetes-master:127.0.0.1 -t ${REPOSITORY} .
# Runs the docker image
run:
	docker run ${REPOSITORY}
run-exe:
	docker run --entrypoint /bin/sh -it ${REPOSITORY}
image-push:
	docker push ${REPOSITORY}:${TAGNAME}
get-cluster-keys:
	bash ./get-cluster-keys.sh

gk: get-cluster-keys
br: build run
be: build run-exe
bi: build image-push