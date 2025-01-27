Docker image
************

We provide a docker image (defined in :gh_blob:`Dockerfile`) that can be used to
easily get an instance of CMS running locally with all the necessary
dependencies. We also provide:

* :gh_blob:`cms-test.sh`: This file uses :gh_blob:`docker-compose.test.yml` to
     spawn a volatile database (not persisted on disk) as well as a CMS instance
     that automatically runs all tests.

* :gh_blob:`cms-dev.sh`: This file uses :gh_blob:`docker-compose.dev.yml` to
     spawn a database (persisted in the local ``.dev/postgres-data`` folder
     within the repository) as well as a CMS instance that only runs `bash`,
     leaving you with a shell from where you can start cms services and servers.
     The DB port and CMS server ports are also automatically forwarded on the
     host machine (respectively to ``15432`` for the database, and ``8888-8890``
     for CMS).

Make sure that you have a recent version of Docker installed, as well as Docker
Compose.

.. _docker-image_running-tests:

Running tests
=============

You can simply run:

.. sourcecode:: bash

    ./cms-test.sh

Or, you can issue the full command (that is defined in ``cms-test.sh``) which
is similar to:

.. sourcecode:: bash

    docker compose -p someprojectname -f docker-compose.test.yml run --build --rm testcms

.. note::

    Some versions of docker require to specify ``-p``, some version will fill it
    for you based on the current folder's name (which for us would be equivalent
    to passing ``-p cms``).

    The ``-p`` flag is used as a namespace for the containers that will be
    created. When you're running tests on a separate branch, it can be useful to
    include the branch name there, to avoid any conflict. The ``cms-test.sh``
    script uses the **name of the current git branch** and passes it to ``-p``.

    Note also that if you are not part of the ``docker`` group then you'll need
    to run every docker command with ``sudo``, including ``sudo ./cms-test.sh``.
    We recommend adding yourself to the ``docker`` group.

What the ``cms-test.sh`` command does is: first build a fresh CMS image when
necessary, and then create (assuming you are on the ``main`` git branch) a
``main-testdb-1`` container for the database, and a
``main-testcms-run-<random_string>`` container for CMS.

The database container **will not** be automatically deleted, while the CMS
container will be automatically deleted upon exiting (because of the ``--rm``
flag).

To delete the ``cms-testdb-1`` container after testing you can run:

.. sourcecode:: bash

    docker rm -f cms-testdb-1

Developing CMS
==============

To run a local development instance of CMS, you can simply run:

.. sourcecode:: bash

    ./cms-dev.sh

Or, you can issue the full command (that is defined in ``cms-dev.sh``) which is
similar to:

.. sourcecode:: bash

    docker compose -p someprojectname -f docker-compose.dev.yml run --build --rm --service-ports devcms

The command will build a fresh CMS image when necessary, and drop you into a
bash prompt where the repository is mounted on ``~/cms`` for ease of
development. You can edit the code from the host (i.e. outside the container)
and then reinstall CMS (``python3 setup.py install``) directly from inside the
container, without having to rebuild the image every time.

Upon running ``cms-dev.sh`` for the first time, the database will initially be
empty. You need to initialize it (notice that the following commands are
indicated with a ``>>>`` prompt because they are meant to be executed **inside**
the container, from the prompt that you get to after running ``cms-dev.sh``)
like so:

.. sourcecode:: bash

    >>> createdb -h devdb -U postgres cmsdb
    >>> cmsInitDB

Then you probably want to download a test contest and import it, for example
like this:

.. sourcecode:: bash

    >>> git clone https://github.com/cms-dev/con_test.git
    >>> cd con_test
    >>> cmsImportUser --all
    >>> cmsImportContest -i .

If this succeeds, you can then run one of the servers, for example the
ContestWebServer, like so:

.. sourcecode:: bash

    >>> cmsContestWebServer

When it prompts you to choose a contest ID, you can simply hit Enter.

When the server is finally running, you can check (from the host machine) that
the server is reachable at http://localhost:8888/

You can also verify that upon exiting the container's bash shell and reentering
it (by running ``cms-dev.sh`` again) you won't need to re-import the contest, as
the database is persisted on disk on the host machine. Even manually destroying
and recreating the database container will retain the same data. If for some
reason you need to reset the database, we recommend using the ``dropdb -h devdb
-U postgres cmsdb`` command inside the container. To remove any trace of the
database data, you can delete the ``.dev/postgres-data`` folder within the git
repository.
