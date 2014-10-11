FROM ubuntu:14.04
MAINTAINER Luca Versari <veluca93@gmail.com>
RUN apt-get update
RUN apt-get -y install build-essential fpc postgresql postgresql-client gettext python2.7 python-setuptools python-tornado python-psycopg2 python-sqlalchemy python-psutil python-netifaces python-crypto python-tz python-six iso-codes shared-mime-info stl-manual python-beautifulsoup python-mechanize python-coverage python-mock cgroup-lite python-requests python-werkzeug python-gevent python-yaml python-sphinx
RUN apt-get install -y openssh-server supervisor
RUN mkdir -p /var/run/sshd /var/log/supervisor
RUN sed -i 's/StrictModes yes/StrictModes no/' /etc/ssh/sshd_config
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
CMD cgroups-mount && /usr/bin/supervisord
EXPOSE 22 8888 8889 8890
ADD . /cms
RUN cd /cms && ./setup.py build && ./setup.py install && rm -rf /cms
