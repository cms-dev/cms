Docker image
************

We provide a docker image (defined in :gh_blob:`Dockerfile`) that can be used to
easily get an instance of CMS running locally with all the necessary
dependencies. We also provide a :gh_blob:`docker-compose.test.yml` files that
uses said docker image to run the tests.

Make sure that you have a recent version of Docker installed, as well as Docker
Compose.

.. _docker-image_running-tests:

Running tests
=============

First you need to build the docker image, then you use it to run the tests.

.. note::

    The ``-p`` flag is used as a namespace for the containers that will be
    created. When you're running tests on a separate branch, it can be useful to
    include the branch name there, to avoid any conflict. (You can also omit the
    flag and specify the name via the ``COMPOSE_PROJECT_NAME`` environment
    variable.)

    If you are not part of the ``docker`` group, then you need to run every
    docker command with ``sudo``.

To build the image:

.. sourcecode:: bash

    docker compose -p cms -f docker-compose.test.yml build testcms

To run the tests:

.. sourcecode:: bash

    docker compose -p cms -f docker-compose.test.yml run --rm testcms

Another option is to add the ``--build`` flag to the ``run`` command, to perform
a new build before running the tests:

.. sourcecode:: bash

    docker compose -p cms -f docker-compose.test.yml run --build --rm testcms

This command will create (assuming you used ``-p cms``) a ``cms-testdb-1``
container for the database which **will not** be automatically deleted, and a
``cms-testcms-run-<random_string>`` container for CMS which will be
automatically deleted (because of the ``--rm`` flag) upon exiting.

To delete the ``cms-testdb-1`` container after testing you can run:

.. sourcecode:: bash

    docker rm -f cms-testdb-1
