# Build an image that can do inference in AWS SageMaker
# This is a Python 3 image that uses the nginx, gunicorn, flask stack
# for serving inferences in a stable way.

#FROM ubuntu:latest
FROM ubuntu:bionic-20191202

MAINTAINER Michael Pilosov

# get the basics
RUN apt-get -y update && apt-get install -y --no-install-recommends \
         build-essential \
         python3-pip \
         python3-dev \
         nginx \
         ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# overwrite the link to system python and upgrade pip
RUN ln -s /usr/bin/python3 /usr/bin/python \
    && pip3 install --upgrade pip

# There's substantial overlap between scipy and numpy that we eliminate by
# linking them together. Likewise, pip leaves the install caches populated which uses
# a significant amount of space. These optimizations save a fair amount of space in the
# image, which reduces start up time.
COPY requirements.txt /tmp/
RUN pip3 install -r /tmp/requirements.txt

# cleanup step to make the image lighter
RUN (cd /usr/local/lib/python3.6/dist-packages/scipy/.libs && rm * && ln ../../numpy/.libs/* .) && \
        rm -rf /root/.cache

# Set some environment variables. PYTHONUNBUFFERED keeps Python from buffering our standard
# output stream, which means that logs can be delivered to the user quickly. PYTHONDONTWRITEBYTECODE
# keeps Python from writing the .pyc files which are unnecessary in this case. We also update
# PATH so that the  serve program is found when the container is invoked.

ENV PYTHONUNBUFFERED=TRUE
ENV PYTHONDONTWRITEBYTECODE=TRUE
ENV PATH="/opt/program:${PATH}"

# Set up the program in the image
COPY model/ /opt/program
WORKDIR /opt/program

# TODO: make a safeuser and try to run this as them (including the pip installs and COPY)
