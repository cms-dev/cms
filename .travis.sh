#!/usr/bin/env bash

sudo apt-get update -qq
sudo apt-get install -y build-essential fpc postgresql postgresql-client \
     gettext python2.7 iso-codes shared-mime-info stl-manual cgroup-lite
sudo apt-get install python-dev libpq-dev libcups2-dev libyaml-dev
sudo apt-get install nginx-full php5-cli php5-fpm phppgadmin \
     texlive-latex-base a2ps

mkdir -p virtualenv/python2.7
virtualenv --python=python2.7 ~/virtualenv/python2.7
source ~/virtualenv/python2.7/bin/activate

cp ./config/cms.conf.sample ./config/cms.conf
./prerequisites.py build -y
sudo ./prerequisites.py install -y

pip install -r requirements.txt
pip install -r dev-requirements.txt
pip install .

sudo su postgres -c "psql -c \"CREATE USER cmsuser WITH PASSWORD 'password';\""
sudo su postgres -c "psql -c \"CREATE DATABASE database WITH OWNER cmsuser;\""
sudo su postgres -c "psql database -c \"ALTER SCHEMA public OWNER TO cmsuser\""
sudo su postgres -c "psql database -c \"GRANT SELECT ON pg_largeobject TO cmsuser\""

./scripts/cmsInitDB

sudo chown root:$USER /usr/local/bin/isolate
sudo chmod 777 /usr/local/bin/isolate
sudo chmod u+s /usr/local/bin/isolate
ls -al /usr/local/bin/isolate
sudo rm -rf ./isolate/isolate
groups

./cmstestsuite/RunTests.py -v
