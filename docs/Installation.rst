Installation
************

Overview
========

CMS runs on Linux. We test it on Debian and Ubuntu, but any modern
distribution should work, too.

You can run CMS as a Docker container. If you want to do so, please
continue to the :doc:`container installation instructions <Docker image>`.

Otherwise, please follow this chapter, which explains how to install CMS
and its dependencies.

.. _installation_dependencies:


Dependencies and available compilers
====================================

These are our requirements (in particular we highlight those that are not usually installed by default) - previous versions may or may not work:

* `PostgreSQL <http://www.postgresql.org/>`_ >= 9.4;

  .. We need 9.4 because of the JSONB data type.

* `GNU compiler collection <https://gcc.gnu.org/>`_ (in particular the C compiler ``gcc``);

* `Python <http://www.python.org/>`_ >= 3.11;

* `Isolate <https://github.com/ioi/isolate/>`_ >= 2.0;

You will also require a Linux kernel with support for `cgroupv2 <https://docs.kernel.org/admin-guide/cgroup-v2.html>`_.
Most Linux distributions provide such kernels by default.

Then you require the compilation and execution environments for the languages you will use in your contest:

* `GNU compiler collection <https://gcc.gnu.org/>`_ (for C and C++, respectively with executables ``gcc`` and ``g++``);

* for Java, your choice of a JDK, for example OpenJDK (but any other JDK behaving similarly is fine, for example Oracle's);

* `Free Pascal <http://www.freepascal.org/>`_ (for Pascal, with executable ``fpc``);

* `Python <http://www.python.org/>`_ (for Python, with executable ``python3``; in addition you will need ``zip``);

* `PHP <http://www.php.net>`_ (for PHP, with executable ``php``);

* `Glasgow Haskell Compiler <https://www.haskell.org/ghc/>`_ (for Haskell, with executable ``ghc``);

* `Rust <https://www.rust-lang.org/>`_ (for Rust, with executable ``rustc``);

* `C# <http://www.mono-project.com/docs/about-mono/languages/csharp/>`_ (for C#, with executable ``mcs``).

All dependencies can be installed automatically on most Linux distributions.

Ubuntu
------

On Ubuntu 24.04, one will need to run the following script as root to satisfy all dependencies:

.. sourcecode:: bash

    # Feel free to change OpenJDK packages with your preferred JDK.
    apt install build-essential openjdk-11-jdk-headless fp-compiler \
        postgresql postgresql-client python3.12 python3.12-dev python3-pip \
        python3-venv libpq-dev libyaml-dev libffi-dev shared-mime-info \
        cppreference-doc-en-html zip curl

    # Isolate from upstream package repository
    echo 'deb [arch=amd64 signed-by=/etc/apt/keyrings/isolate.asc] http://www.ucw.cz/isolate/debian/ noble-isolate main' >/etc/apt/sources.list.d/isolate.list
    curl https://www.ucw.cz/isolate/debian/signing-key.asc >/etc/apt/keyrings/isolate.asc
    apt update && apt install isolate

    # Optional
    apt install nginx-full php-cli ghc rustc mono-mcs pypy3

The above commands provide a very essential Pascal environment. Consider installing the following packages for additional units: ``fp-units-base``, ``fp-units-fcl``, ``fp-units-misc``, ``fp-units-math`` and ``fp-units-rtl``.

Arch Linux
----------

On Arch Linux, run the following commands as root to install almost all dependencies
(some of them can be found in the AUR):

.. sourcecode:: bash

    pacman -S base-devel jdk8-openjdk fpc postgresql postgresql-client \
        python python-pip postgresql-libs libyaml shared-mime-info

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/cppreference/
    # https://aur.archlinux.org/packages/isolate

    # Optional
    pacman -S --needed nginx php php-fpm phppgadmin ghc rust mono pypy3


Preparation steps
=================

We recommend to create a new user account for CMS, usually called ``cmsuser``:

.. sourcecode:: bash

    sudo useradd --user-group --create-home --comment CMS cmsuser

If you are using a packaged version of Isolate, you need to add ``cmsuser``
to the ``isolate`` group:

.. sourcecode:: bash

    sudo usermod -a -G isolate cmsuser


Installing CMS
==============

The installation of CMS should be performed as the ``cmsuser``.

First obtain the source code of CMS. Download :gh_download:`CMS release`
|release| from GitHub as an archive, extract it and start a shell inside.
Alternatively, if you like living at the bleeding edge, check out the CMS
`Git repository <https://github.com/cms-dev/cms>`_ instead.

The preferred method of installation is using :samp:`./install.py --dir={install_dir} cms`,
which does the following:

* Creates an *installation directory* of the given name. It contains a Python
  virtual environment and subdirectories where CMS stores its data, logs, and caches.
  If you omit the ``--dir`` option, CMS is installed to ``~/cms`` (``cms`` in the
  home directory of the current user). Make sure that it is different from the
  source directory.

* Populates the virtual environment with CMS and Python packages on which CMS depends.

* Checks that Isolate is available.

* Installs the sample configuration files to :samp:`{install_dir}/etc/cms.toml`
  and :samp:`{install_dir}/etc/cms_ranking.toml`.

Now you can run CMS commands from the shell directly as :samp:`{install_dir}/bin/{command}`.
It is usually more convenient to activate the virtual environment, which adds
:samp:`{install_dir}/bin` to your ``$PATH``. This can be done by adding the following line
to your ``~/.profile``:

.. sourcecode:: bash

    source $TARGET/bin/activate

(with ``$TARGET`` replaced by the path to your installation directory).


Development installs
--------------------

If you want to develop CMS, you can use :samp:`./install.py --dir={install_dir} cms --devel --editable`.
This includes development dependencies. It also makes the installation linked to the
source directory, so you don't need to reinstall if you edit the source.


Configuring the worker machines
===============================

Worker machines need to be carefully set up in order to ensure that evaluation
results are valid and consistent. Just running the evaluations under Isolate
does not achieve this: for example, if the machine has CPU power management
configured, it might affect execution time in an unpredictable way.
Having an active swap partition may allow programs to evade memory limits.

We suggest following Isolate's `guidelines <https://www.ucw.cz/isolate/isolate.1.html#_reproducibility>`_ for reproducible results
and running the ``isolate-check-environment`` command which checks your system
for common issues.


.. _installation_updatingcms:

Updating CMS
============

As CMS develops, the database schema it uses to represent its data may be updated and new versions may introduce changes that are incompatible with older versions.

To preserve the data stored on the database you need to dump it on the filesystem using ``cmsDumpExporter`` **before you update CMS** (i.e. with the old version).

You can then update CMS and reset the database schema by running:

.. sourcecode:: bash

    cmsDropDB
    cmsInitDB

To load the previous data back into the database you can use ``cmsDumpImporter``: it will adapt the data model automatically on-the-fly (you can use ``cmsDumpUpdater`` to store the updated version back on disk and speed up future imports).
