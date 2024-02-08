# syntax=docker/dockerfile:1
FROM ubuntu:20.04

RUN apt-get update
RUN apt-get install -y \
    build-essential \
    cgroup-lite \
    cppreference-doc-en-html \
    fp-compiler \
    git \
    haskell-platform \
    libcap-dev \
    libcups2-dev \
    libffi-dev \
    libpq-dev \
    libyaml-dev \
    mono-mcs \
    openjdk-8-jdk-headless \
    php7.4-cli \
    postgresql-client \
    python2 \
    python3-pip \
    python3.8 \
    python3.8-dev \
    rustc \
    sudo \
    wait-for-it \
    zip

# Create cmsuser user with sudo privileges
RUN useradd -ms /bin/bash cmsuser && \
    usermod -aG sudo cmsuser
# Disable sudo password
RUN echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
# Set cmsuser as default user
USER cmsuser

RUN mkdir /home/cmsuser/cms
COPY --chown=cmsuser:cmsuser requirements.txt dev-requirements.txt /home/cmsuser/cms/

WORKDIR /home/cmsuser/cms

RUN sudo pip3 install -r requirements.txt
RUN sudo pip3 install -r dev-requirements.txt

COPY --chown=cmsuser:cmsuser . /home/cmsuser/cms

RUN sudo python3 setup.py install

RUN sudo python3 prerequisites.py --yes --cmsuser=cmsuser install

RUN sudo sed 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@testdb:5432/cmsdbfortesting"|' ./config/cms.conf.sample \
    | sudo tee /usr/local/etc/cms-testdb.conf

ENV LANG C.UTF-8

CMD [""]
