Installation
************

.. _installation_dependencies:

Dependencies and available compilers
====================================

These are our requirements (in particular we highlight those that are not usually installed by default) - previous versions may or may not work:

* build environment for the programming languages allowed in the competition;

* `PostgreSQL <http://www.postgresql.org/>`_ >= 9.4;

  .. We need 9.4 because of the JSONB data type.

* `GNU compiler collection <https://gcc.gnu.org/>`_ (in particular the C compiler ``gcc``);

* `Python <http://www.python.org/>`_ >= 3.8;

* `libcg <http://libcg.sourceforge.net/>`_;

* `TeX Live <https://www.tug.org/texlive/>`_ (only for printing);

* `a2ps <https://www.gnu.org/software/a2ps/>`_ (only for printing).

You will also require a Linux kernel with support for control groups and namespaces. Support has been in the Linux kernel since 2.6.32. Other distributions, or systems with custom kernels, may not have support enabled. At a minimum, you will need to enable the following Linux kernel options: ``CONFIG_CGROUPS``, ``CONFIG_CGROUP_CPUACCT``, ``CONFIG_MEMCG`` (previously called as ``CONFIG_CGROUP_MEM_RES_CTLR``), ``CONFIG_CPUSETS``, ``CONFIG_PID_NS``, ``CONFIG_IPC_NS``, ``CONFIG_NET_NS``. It is anyway suggested to use Linux kernel version at least 3.8.

Then you require the compilation and execution environments for the languages you will use in your contest:

* `GNU compiler collection <https://gcc.gnu.org/>`_ (for C and C++, respectively with executables ``gcc`` and ``g++``);

* for Java, your choice of a JDK, for example OpenJDK (but any other JDK behaving similarly is fine, for example Oracle's);

* `Free Pascal <http://www.freepascal.org/>`_ (for Pascal, with executable ``fpc``);

* `Python <http://www.python.org/>`_ >= 2.7 (for Python, with executable ``python2`` or ``python3``; in addition you will need ``zip``);

* `PHP <http://www.php.net>`_ >= 5 (for PHP, with executable ``php``);

* `Glasgow Haskell Compiler <https://www.haskell.org/ghc/>`_ (for Haskell, with executable ``ghc``);

* `Rust <https://www.rust-lang.org/>`_ (for Rust, with executable ``rustc``);

* `C# <http://www.mono-project.com/docs/about-mono/languages/csharp/>`_ (for C#, with executable ``mcs``).

All dependencies can be installed automatically on most Linux distributions.

Ubuntu
------

On Ubuntu 20.04, one will need to run the following script to satisfy all dependencies:

.. sourcecode:: bash

    # Feel free to change OpenJDK packages with your preferred JDK.
    sudo apt-get install build-essential openjdk-11-jdk-headless fp-compiler \
        postgresql postgresql-client python3.8 cppreference-doc-en-html \
        cgroup-lite libcap-dev zip

    # Only if you are going to use pip/venv to install python dependencies
    sudo apt-get install python3.8-dev libpq-dev libcups2-dev libyaml-dev \
        libffi-dev python3-pip

    # Optional
    sudo apt-get install nginx-full python2.7 php7.4-cli php7.4-fpm \
        phppgadmin texlive-latex-base a2ps haskell-platform rustc mono-mcs

The above commands provide a very essential Pascal environment. Consider installing the following packages for additional units: `fp-units-base`, `fp-units-fcl`, `fp-units-misc`, `fp-units-math` and `fp-units-rtl`.

Arch Linux
----------

On Arch Linux, unofficial AUR packages can be found: `cms <http://aur.archlinux.org/packages/cms>`_ or `cms-git <http://aur.archlinux.org/packages/cms-git>`_. However, if you do not want to use them, the following command will install almost all dependencies (some of them can be found in the AUR):

.. sourcecode:: bash

    sudo pacman -S base-devel jdk8-openjdk fpc postgresql postgresql-client \
        python libcap

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/libcgroup/
    # https://aur.archlinux.org/packages/cppreference/

    # Only if you are going to use pip/venv to install python dependencies
    sudo pacman -S --needed postgresql-libs libcups libyaml python-pip

    # Optional
    sudo pacman -S --needed nginx python2 php php-fpm phppgadmin texlive-core \
        a2ps ghc rust mono

Preparation steps
=================

Download :gh_download:`CMS` |release| from GitHub as an archive, then extract it on your filesystem. You should then access the ``cms`` folder using a terminal.

.. warning::

    If you decided to ``git clone`` the repository instead of downloading the archive, and you didn't use the ``--recursive`` option when cloning, then **you need** to issue the following command to fetch the source code of the sandbox:

    .. sourcecode:: bash

        git submodule update --init

In order to run CMS there are some preparation steps to run (like installing the sandbox, compiling localization files, creating the ``cmsuser``, and so on). You can either do all these steps by hand or you can run the following command:

.. sourcecode:: bash

    sudo python3 prerequisites.py install

.. FIXME -- The following part probably does not need to be mentioned. Moreover, it would be better if isolate was just a dependency (like postgresql) to be installed separately, with its own group (e.g. 'isolate' instead of 'cmsuser'). The 'cmsuser' group could just become deprected, at that point.

This script will add you to the ``cmsuser`` group if you answer ``Y`` when asked. If you want to handle your groups by yourself, answer ``N`` and then run:

.. sourcecode:: bash

    sudo usermod -a -G cmsuser <your user>

You can verify to be in the group by issuing the command:

.. sourcecode:: bash

    groups

Remember to logout, to make the change effective.

.. warning::

   Users in the group ``cmsuser`` will be able to launch the ``isolate`` program with root permission. They may exploit this to gain root privileges. It is then imperative that no untrusted user is allowed in the group ``cmsuser``.

.. _installation_updatingcms:


Installing CMS and its Python dependencies
==========================================

There are a number of ways to install CMS and its Python dependencies:

Method 1: Global installation with pip
--------------------------------------

There are good reasons to install CMS and its Python dependencies via pip (Python Package Index) instead of your package manager (e.g. apt-get). For example: two different Linux distro (or two different versions of the same distro) may offer two different versions of ``python-sqlalchemy``. When using pip, you can choose to install a *specific version* of ``sqlalchemy`` that is known to work correctly with CMS.

Assuming you have ``pip`` installed, you can do this:

.. sourcecode:: bash

    export SETUPTOOLS_USE_DISTUTILS="stdlib"
    sudo --preserve-env=SETUPTOOLS_USE_DISTUTILS pip3 install -r requirements.txt
    sudo --preserve-env=SETUPTOOLS_USE_DISTUTILS python3 setup.py install

This command installs python dependencies globally. Note that on some distros, like Arch Linux, this might interfere with the system package manager. If you want to perform the installation in your home folder instead, then you can do this instead:

.. sourcecode:: bash

    export SETUPTOOLS_USE_DISTUTILS="stdlib"
    pip3 install --user -r requirements.txt
    python3 setup.py install --user

Method 2: Virtual environment
-----------------------------

An alternative method to perform the installation is with a `virtual environment <https://virtualenv.pypa.io/en/latest/>`_, which is an isolated Python environment that you can put wherever you like and that can be activated/deactivated at will.

You will need to create a virtual environment somewhere in your filesystem. For example, let's assume that you decided to create it under your home directory (as ``~/cms_venv``):

.. sourcecode:: bash

    python3 -m venv ~/cms_venv

To activate it:

.. sourcecode:: bash

    source ~/cms_venv/bin/activate

After the activation, the ``pip`` command will *always* be available (even if it was not available globally, e.g. because you did not install it). In general, every python command (python, pip) will refer to their corresponding virtual version. So, you can install python dependencies by issuing:

.. sourcecode:: bash

    export SETUPTOOLS_USE_DISTUTILS="stdlib"
    pip3 install -r requirements.txt
    python3 setup.py install

.. note::

    Once you finished using CMS, you can deactivate the virtual environment by issuing:

    .. sourcecode:: bash

        deactivate

Method 3: Using ``apt-get`` on Ubuntu
-------------------------------------

.. warning::

  It is usually possible to install python dependencies using your Linux distribution's package manager. However, keep in mind that the version of each package is controlled by the package mantainers and could be too new or too old for CMS. **On Ubuntu, this is generally not the case** since we try to build on the python packages that are available for the current LTS version.

.. warning::

  On Ubuntu 20.04, the shipped version of ``python3-gevent`` is too old to support the system Python 3 version. After installing other packages from the repositories, you should still install ``gevent>=1.5,<1.6``, for example, using the ``pip`` method above.

To install CMS and its Python dependencies on Ubuntu, you can issue:

.. sourcecode:: bash

    sudo python3 setup.py install

    sudo apt-get install python3-setuptools python3-tornado4 python3-psycopg2 \
         python3-sqlalchemy python3-psutil python3-netifaces python3-pycryptodome \
         python3-bs4 python3-coverage python3-requests python3-werkzeug \
         python3-gevent python3-bcrypt python3-chardet patool python3-babel \
         python3-xdg python3-jinja2

    # Optional.
    # sudo apt-get install python3-yaml python3-sphinx python3-cups python3-pypdf2

Method 4: Using ``pacman`` on Arch Linux
----------------------------------------

.. warning::

  It is usually possible to install python dependencies using your Linux distribution's package manager. However, keep in mind that the version of each package is controlled by the package mantainers and could be too new or too old for CMS. **This is especially true for Arch Linux**, which is a bleeding edge distribution.

To install CMS python dependencies on Arch Linux (again: assuming you did not use the aforementioned AUR packages), you can issue:

.. sourcecode:: bash

    sudo python3 setup.py install

    sudo pacman -S --needed python-setuptools python-tornado python-psycopg2 \
         python-sqlalchemy python-psutil python-netifaces python-pycryptodome \
         python-beautifulsoup4 python-coverage python-requests python-werkzeug \
         python-gevent python-bcrypt python-chardet python-babel python-xdg \
         python-jinja

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/patool/

    # Optional.
    # sudo pacman -S --needed python-yaml python-sphinx python-pycups
    # Optionally install the following from AUR.
    # https://aur.archlinux.org/packages/python-pypdf2/


Configuring the worker machines
===============================

Worker machines need to be carefully set up in order to ensure that evaluation results are valid and consistent. Just running the evaluations under isolate does not achieve this: for example, if the machine has an active swap partition, memory limit will not be honored.

Apart from validity, there are many possible tweaks to reduce the variability in resource usage of an evaluation.

We suggest following isolate's `guidelines <https://github.com/ioi/isolate/blob/c679ae936d8e8d64e5dab553bdf1b22261324315/isolate.1.txt#L292>`_ for reproducible results.


.. _installation_running-cms-non-installed:

Running CMS non-installed
=========================

To run CMS without installing it in the system, you need first to build the prerequisites:

.. sourcecode:: bash

    python3 prerequisites.py build

There are still a few steps to complete manually in this case. First, add CMS and isolate to the path and create the configuration files:

.. sourcecode:: bash

    export PATH=$PATH:./isolate/
    export PYTHONPATH=./
    cp config/cms.conf.sample config/cms.conf
    cp config/cms.ranking.conf.sample config/cms.ranking.conf

Second, perform these tasks (that require root permissions):

* create the ``cmsuser`` user and a group with the same name;

* add your user to the ``cmsuser`` group;

* set isolate to be owned by root:cmsuser, and set its suid bit.

For example:

.. sourcecode:: bash

    sudo useradd cmsuser
    sudo usermod -a -G cmsuser <your user>
    sudo chown root:cmsuser ./isolate/isolate
    sudo chmod u+s ./isolate/isolate

Updating CMS
============

As CMS develops, the database schema it uses to represent its data may be updated and new versions may introduce changes that are incompatible with older versions.

To preserve the data stored on the database you need to dump it on the filesystem using ``cmsDumpExporter`` **before you update CMS** (i.e. with the old version).

You can then update CMS and reset the database schema by running:

.. sourcecode:: bash

    cmsDropDB
    cmsInitDB

To load the previous data back into the database you can use ``cmsDumpImporter``: it will adapt the data model automatically on-the-fly (you can use ``cmsDumpUpdater`` to store the updated version back on disk and speed up future imports).
