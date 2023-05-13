Docker image
************

We provide a docker image (defined in :gh_blob:`Dockerfile`) that can be used to
easily get an instance of CMS running locally with all the necessary
dependencies. We also provide a :gh_blob:`docker-compose.test.yml` files that
uses said docker image to run the tests.

.. _docker-image_running-tests:

Running tests
=============

First you need to build the image:

.. sourcecode:: bash

    sudo docker-compose -f docker-compose.test.yml build cms_test

Then you can run the tests:

.. sourcecode:: bash

    sudo docker-compose -f docker-compose.test.yml run --rm cms_test

This command will create a ``cms_test_db`` container for the database which
**will not** be automatically deleted, and a ``cms_test`` container for CMS
which will be automatically deleted (because of the ``--rm`` flag) upon exiting.

To delete the ``cms_test_db`` container after testing you can run:

.. sourcecode:: bash

    sudo docker rm -f cms_test_db
