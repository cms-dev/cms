Installation
************

.. _installation_dependencies:

Dependencies and available compilers
====================================

These are our requirements (in particular we highlight those that are not usually installed by default) - previous versions may or may not work:

* build environment for the programming languages allowed in the competition;

* `PostgreSQL <http://www.postgresql.org/>`_ >= 9.0;

  .. We need 9.0 because of pg_largeobject_metadata (in drop_db).

* `GNU compiler collection <https://gcc.gnu.org/>`_ (in particular the C compiler ``gcc``);

* `gettext <http://www.gnu.org/software/gettext/>`_ >= 0.18;

* `Python <http://www.python.org/>`_ >= 2.7, < 3.0;

* `libcg <http://libcg.sourceforge.net/>`_;

* `iso-codes <http://pkg-isocodes.alioth.debian.org/>`_;

* `shared-mime-info <http://freedesktop.org/wiki/Software/shared-mime-info>`_;

* `TeX Live <https://www.tug.org/texlive/>`_ (only for printing);

* `a2ps <https://www.gnu.org/software/a2ps/>`_ (only for printing).

You will also require a Linux kernel with support for control groups and namespaces. Support has been in the Linux kernel since 2.6.32. Other distributions, or systems with custom kernels, may not have support enabled. At a minimum, you will need to enable the following Linux kernel options: ``CONFIG_CGROUPS``, ``CONFIG_CGROUP_CPUACCT``, ``CONFIG_MEMCG`` (previously called as ``CONFIG_CGROUP_MEM_RES_CTLR``), ``CONFIG_CPUSETS``, ``CONFIG_PID_NS``, ``CONFIG_IPC_NS``, ``CONFIG_NET_NS``. It is anyway suggested to use Linux kernel version at least 3.8.

Then you require the compilation and execution environments for the languages you will use in your contest:

* `GNU compiler collection <https://gcc.gnu.org/>`_ (for C, C++ and Java, respectively with executables ``gcc``, ``g++`` and ``gcj``);

* alternatively, for Java, your choice of a JDK, for example OpenJDK (but any other JDK behaving similarly is fine, for example Oracle's);

* `Free Pascal <http://www.freepascal.org/>`_ (for Pascal, with executable ``fpc``);

* `Python <http://www.python.org/>`_ >= 2.7, < 3.0 (for Python, with executable ``python2``; note though that this must be installed anyway because it is required by CMS itself);

* `PHP <http://www.php.net>`_ >= 5 (for PHP, with executable ``php``);

* `Glasgow Haskell Compiler <https://www.haskell.org/ghc/>`_ (for Haskell, with executable ``ghc``);

* `Rust <https://www.rust-lang.org/>`_ (for Rust, with executable ``rustc``);

* `C# <http://www.mono-project.com/docs/about-mono/languages/csharp/>` (for C#, with executable ``mcs``).

All dependencies can be installed automatically on most Linux distributions.

Ubuntu
------

On Ubuntu 16.04, one will need to run the following script to satisfy all dependencies:

.. sourcecode:: bash

    # Feel free to change OpenJDK packages with your preferred JDK.
    sudo apt-get install build-essential openjdk-8-jre openjdk-8-jdk \
        fp-compiler fp-units-base fp-units-fcl fp-units-misc fp-units-math fp-units-rtl \
        postgresql postgresql-client gettext python2.7 \
        iso-codes shared-mime-info stl-manual cgroup-lite libcap-dev

    # Only if you are going to use pip/virtualenv to install python dependencies
    sudo apt-get install python-dev libpq-dev libcups2-dev libyaml-dev \
         libffi-dev python-pip

    # Optional
    sudo apt-get install nginx-full php7.0-cli php7.0-fpm phppgadmin \
         texlive-latex-base a2ps gcj-jdk haskell-platform rustc mono-mcs

Arch Linux
----------

On Arch Linux, unofficial AUR packages can be found: `cms <http://aur.archlinux.org/packages/cms>`_ or `cms-git <http://aur.archlinux.org/packages/cms-git>`_. However, if you do not want to use them, the following command will install almost all dependencies (some of them can be found in the AUR):

.. sourcecode:: bash

    sudo pacman -S base-devel jre8-openjdk jdk8-openjdk fpc \
         postgresql postgresql-client python2 \
         iso-codes shared-mime-info libcap

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/libcgroup/
    # https://aur.archlinux.org/packages/sgi-stl-doc/

    # Only if you are going to use pip/virtualenv to install python dependencies
    sudo pacman -S --needed postgresql-libs libcups libyaml python2-pip

    # Optional
    sudo pacman -S --needed nginx php php-fpm phppgadmin texlive-core a2ps \
         ghc rust mono

Preparation steps
=================

Download :gh_download:`CMS` |release| from GitHub as an archive, then extract it on your filesystem. You should then access the ``cms`` folder using a terminal.

.. warning::

    If you decided to ``git clone`` the repository instead of downloading the archive, and you didn't use the ``--recursive`` option when cloning, then **you need** to issue the following command to fetch the source code of the sandbox:

    .. sourcecode:: bash

        git submodule update --init

In order to run CMS there are some preparation steps to run (like installing the sandbox, compiling localization files, creating the ``cmsuser``, and so on). You can either do all these steps by hand or you can run the following command:

.. sourcecode:: bash

    sudo ./prerequisites.py install

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

    sudo pip2 install -r requirements.txt
    sudo python2 setup.py install

This command installs python dependencies globally. Note that on some distros, like Arch Linux, this might interfere with the system package manager. If you want to perform the installation in your home folder instead, then you can do this instead:

.. sourcecode:: bash

    pip2 install --user -r requirements.txt
    python2 setup.py install --user

Method 2: Virtual environment
-----------------------------

.. warning::

An alternative method to perform the installation is with a `virtual environment <https://virtualenv.pypa.io/en/latest/>`_, which is an isolated Python environment that you can put wherever you like and that can be activated/deactivated at will. The tool you need in order to create a virtual environment is called ``virtualenv``, and can be installed by looking for ``virtualenv`` using your Linux distribution's package manager. For example:

* Ubuntu 14.x: `python-virtualenv <http://packages.ubuntu.com/trusty/python-virtualenv>`_.
* Ubuntu 16.x: `virtualenv <http://packages.ubuntu.com/xenial/virtualenv>`_.
* Arch Linux: `python-virtualenv <https://www.archlinux.org/packages/extra/any/python-virtualenv/>`_.

.. FUTURE FIXME: virtualenv installation is necessary only on python2; when the
   porting to python3 will be complete, the "new" way of creating a virtual
   environment will be ``pyvenv`` or equivalently ``python -m venv`` (the venv
   module and the pyvenv script come bundled with python3, so there is no need
   to install virtualenv anymore).

Once you installed ``virtualenv``, you will need to create a virtual environment somewhere in your filesystem. For example, let's assume that you decided to create it under your home directory (as ``~/cms_venv``):

.. sourcecode:: bash

    virtualenv -p python2 ~/cms_venv

To activate it:

.. sourcecode:: bash

    source ~/cms_venv/bin/activate

After the activation, the ``pip`` command will *always* be available (even if it was not available globally, e.g. because you did not install it). In general, every python command (python, pip) will refer to their corresponding virtual version. So, you can install python dependencies by issuing:

.. sourcecode:: bash

    pip install -r requirements.txt
    python setup.py install

.. note::

    Once you finished using CMS, you can deactivate the virtual environment by issuing:

    .. sourcecode:: bash

        deactivate

Method 3: Using ``apt-get`` on Ubuntu
-------------------------------------

.. warning::

  It is usually possible to install python dependencies using your Linux distribution's package manager. However, keep in mind that the version of each package is controlled by the package mantainers and could be too new or too old for CMS. **On Ubuntu, this is generally not the case** since we try to build on the python packages that are available for the current LTS version.

To install CMS and its Python dependencies on Ubuntu, you can issue:

.. sourcecode:: bash

    sudo python setup.py install

    sudo apt-get install python-setuptools python-tornado python-psycopg2 \
         python-sqlalchemy python-psutil python-netifaces python-crypto \
         python-tz python-six python-bs4 python-coverage python-mock \
         python-requests python-werkzeug python-gevent python-bcrypt \
         python-chardet patool python-ipaddress

    # Optional.
    # sudo apt-get install python-yaml python-sphinx python-cups python-pypdf2

Method 4: Using ``pacman`` on Arch Linux
----------------------------------------

.. warning::

  It is usually possible to install python dependencies using your Linux distribution's package manager. However, keep in mind that the version of each package is controlled by the package mantainers and could be too new or too old for CMS. **This is especially true for Arch Linux**, which is a bleeding edge distribution.

To install CMS python dependencies on Arch Linux (again: assuming you did not use the aforementioned AUR packages), you can issue:

.. sourcecode:: bash

    sudo python2 setup.py install

    sudo pacman -S --needed python2-setuptools python2-tornado python2-psycopg2 \
         python2-sqlalchemy python2-psutil python2-netifaces python2-crypto \
         python2-pytz python2-six python2-beautifulsoup4 python2-coverage \
         python2-mock python2-requests python2-werkzeug python2-gevent \
         python2-bcrypt python2-chardet python2-ipaddress

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/patool/

    # Optional.
    # sudo pacman -S --needed python2-yaml python-sphinx python2-pycups
    # Optionally install the following from AUR.
    # https://aur.archlinux.org/packages/python2-pypdf2/


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

    ./prerequisites.py build

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
