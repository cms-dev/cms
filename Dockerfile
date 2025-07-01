# syntax=docker/dockerfile:1
FROM ubuntu:24.04

RUN \
    export DEBIAN_FRONTEND=noninteractive ; \
    apt update && \
    apt upgrade -y && \
    apt install -y \
        build-essential \
        cgroup-lite \
        cppreference-doc-en-html \
        curl \
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
        python3-venv \
        python3.12 \
        python3.12-dev \
        rustc \
        shared-mime-info \
        sudo \
        wait-for-it \
        zip

RUN \
    export DEBIAN_FRONTEND=noninteractive ; \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc] http://www.ucw.cz/isolate/debian/ bookworm-isolate main" >/etc/apt/sources.list.d/isolate.list && \
    curl https://www.ucw.cz/isolate/debian/signing-key.asc >/etc/apt/keyrings/isolate.asc && \
    apt update && \
    apt install -y isolate && \
    sed -i 's@^cg_root .*@cg_root = /sys/fs/cgroup@' /etc/isolate

# Create cmsuser user with sudo privileges and access to isolate
RUN \
    useradd -ms /bin/bash cmsuser && \
    usermod -aG sudo cmsuser && \
    usermod -aG isolate cmsuser && \
    # Disable sudo password \
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

# Set cmsuser as default user
USER cmsuser
ENV LANG=C.UTF-8

RUN mkdir /home/cmsuser/src
COPY --chown=cmsuser:cmsuser install.py constraints.txt /home/cmsuser/src/

WORKDIR /home/cmsuser/src

RUN ./install.py venv
ENV PATH="/home/cmsuser/cms/bin:$PATH"

COPY --chown=cmsuser:cmsuser . /home/cmsuser/src

RUN ./install.py cms --devel

RUN sed 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@testdb:5432/cmsdbfortesting"|' ./config/cms.sample.toml >../cms/etc/cms-testdb.toml
RUN sed -e 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@devdb:5432/cmsdb"|' -e 's/127.0.0.1/0.0.0.0/' ./config/cms.sample.toml >../cms/etc/cms-devdb.toml
RUN sed -i 's/127.0.0.1/0.0.0.0/' ../cms/etc/cms_ranking.toml

CMD ["/bin/bash"]
