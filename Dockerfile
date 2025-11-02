# syntax=docker/dockerfile:1
# Supported combinations: ubuntu:noble, debian:bookworm.
ARG BASE_IMAGE=ubuntu:noble
FROM ${BASE_IMAGE}

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked <<EOF
#!/bin/bash -ex
    export DEBIAN_FRONTEND=noninteractive
    # Don't delete all the .deb files after install, as that would make the
    # cache useless.
    rm -f /etc/apt/apt.conf.d/docker-clean
    # Note that we use apt-get here instead of plain apt, because plain apt
    # also deletes .deb files after successful install.
    apt-get update
    apt-get upgrade -y
    PACKAGES=(
        build-essential
        cppreference-doc-en-html
        curl
        default-jdk-headless
        fp-compiler
        ghc
        git
        libcap-dev
        libffi-dev
        libpq-dev
        libyaml-dev
        mono-mcs
        php-cli
        postgresql-client
        pypy3
        python3
        python3-dev
        python3-pip
        python3-venv
        rustc
        shared-mime-info
        sudo
        wait-for-it
        zip
    )
    apt-get install -y "${PACKAGES[@]}"
EOF

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked <<EOF
#!/bin/bash -ex
    export DEBIAN_FRONTEND=noninteractive
    CODENAME=$(source /etc/os-release; echo $VERSION_CODENAME)
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc]" \
        "http://www.ucw.cz/isolate/debian/ ${CODENAME}-isolate main" \
        >/etc/apt/sources.list.d/isolate.list
    curl https://www.ucw.cz/isolate/debian/signing-key.asc \
        >/etc/apt/keyrings/isolate.asc
    apt-get update
    apt-get install -y isolate
    sed -i 's@^cg_root .*@cg_root = /sys/fs/cgroup@' /etc/isolate
EOF

# Create cmsuser user with sudo privileges and access to isolate
RUN <<EOF
#!/bin/bash -ex
    # Need to set user ID manually: otherwise it'd be 1000 on debian
    # and 1001 on ubuntu.
    useradd -ms /bin/bash -u 1001 cmsuser
    usermod -aG sudo cmsuser
    usermod -aG isolate cmsuser
    # Disable sudo password
    echo '%sudo ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers
EOF

# Set cmsuser as default user
USER cmsuser
ENV LANG=C.UTF-8

RUN mkdir /home/cmsuser/src
COPY --chown=cmsuser:cmsuser install.py constraints.txt /home/cmsuser/src/

WORKDIR /home/cmsuser/src

RUN --mount=type=cache,target=/home/cmsuser/.cache/pip,uid=1001 ./install.py venv
ENV PATH="/home/cmsuser/cms/bin:$PATH"

COPY --chown=cmsuser:cmsuser . /home/cmsuser/src

RUN --mount=type=cache,target=/home/cmsuser/.cache/pip,uid=1001 ./install.py cms --devel

RUN <<EOF
#!/bin/bash -ex
    sed 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@testdb:5432/cmsdbfortesting"|' \
        ./config/cms.sample.toml >../cms/etc/cms-testdb.toml
    sed -e 's|/cmsuser:your_password_here@localhost:5432/cmsdb"|/postgres@devdb:5432/cmsdb"|' \
        -e 's/127.0.0.1/0.0.0.0/' \
        ./config/cms.sample.toml >../cms/etc/cms-devdb.toml
    sed -i 's/127.0.0.1/0.0.0.0/' ../cms/etc/cms_ranking.toml
EOF

CMD ["/bin/bash"]
