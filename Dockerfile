# syntax=docker/dockerfile:1
FROM ubuntu:24.04

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential \
    cgroup-lite \
    cppreference-doc-en-html \
    fp-compiler \
    git \
    ghc \
    libcap-dev \
    libcups2-dev \
    libffi-dev \
    libpq-dev \
    libyaml-dev \
    mono-mcs \
    openjdk-8-jdk-headless \
    php-cli \
    postgresql-client \
    pypy3 \
    python3-pip \
    python3.12 \
    python3.12-dev \
    rustc \
    shared-mime-info \
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

RUN sudo pip3 install --break-system-packages -r requirements.txt
RUN sudo pip3 install --break-system-packages -r dev-requirements.txt

COPY --chown=cmsuser:cmsuser . /home/cmsuser/cms

RUN sudo pip3 install --break-system-packages .

RUN sudo python3 prerequisites.py --yes --cmsuser=cmsuser install

RUN sed 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@testdb:5432/cmsdbfortesting"|' ./config/cms.conf.sample \
    | sudo tee /usr/local/etc/cms-testdb.conf
RUN sed -e 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@devdb:5432/cmsdb"|' -e 's/127.0.0.1/0.0.0.0/' ./config/cms.conf.sample \
    | sudo tee /usr/local/etc/cms-devdb.conf
RUN sed 's/127.0.0.1/0.0.0.0/' ./config/cms.ranking.conf.sample | sudo tee /usr/local/etc/cms.ranking.conf

ENV LANG C.UTF-8

CMD [""]
