Installation
************

Dependencies
============

These are our requirements (in particular we highlight those that are not usually installed by default) - previous versions may or may not work:

* build environment for the programming languages allowed in the competition;

* postgreSQL >= 8.4;

* gettext >= 0.18;

* python >= 2.7 (and < 3.0);

* python-setuptools >= 0.6;

* python-tornado >= 2.0;

* python-psycopg2 >= 2.4;

* python-simplejson >= 2.1;

* python-sqlalchemy >= 0.7;

* python-psutil >= 0.2;

* python-netifaces >= 0.5;

* python-crypto >= 2.3;

* python-yaml >= 3.10 (only for YamlImporter);

* python-beautifulsoup >= 3.2 (only for running tests);

* python-mechanize >= 0.2 (only for running tests);

* python-coverage >= 3.4 (only for running tests).


On Ubuntu 12.04, one will need to run the following script to satisfy all dependencies:

.. sourcecode:: bash

    sudo apt-get install postgresql postgresql-client python-setuptools \
         python-tornado python-psycopg2 python-sqlalchemy \
         python-psutil gettext build-essential fpc stl-manual \
         python-simplejson python-netifaces python-beautifulsoup \
         python-coverage python-crypto python-tz iso-codes shared-mime-info

    # Optional.
    # sudo apt-get install phppgadmin python-yaml

If you prefer using Python Package Index, you can retrieve all Python dependencies with this line:

.. sourcecode:: bash

    sudo pip install -r REQUIREMENTS.txt


Installing CMS
==============

You can download CMS |release| from :gh_download:`GitHub` and extract in your filesystem. After that, you can install it (recommended, not necessary though):

.. sourcecode:: bash

    ./setup.py build
    sudo ./setup.py install


If you install CMS, you also need to add your user to the ``cmsuser`` group and logout to make the change effective:

.. sourcecode:: bash

    sudo usermod -a -G cmsuser

You can verify to be in the group issuing the command:

.. sourcecode:: bash

    groups


Updating CMS
============

If you were using CMS before the release of version |release|, you can update the content of your database with:

.. sourcecode:: bash

    cd cms/db
    python UpdateDB.py -l # To see which updating scripts are available.
    python UpdateDB.py -s YYYYMMDD # To update the DB, where YYYYMMDD is
                                   # the last date in which you created or
                                   # updated the DB.

