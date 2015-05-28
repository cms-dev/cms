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

* `TeX Live <https://www.tug.org/texlive/>`_ (only for printing)

* `a2ps <https://www.gnu.org/software/a2ps/>`_ (only for printing)

You will also require a Linux kernel with support for control groups and namespaces. Support has been in the Linux kernel since 2.6.32. Other distributions, or systems with custom kernels, may not have support enabled. At a minimum, you will need to enable the following Linux kernel options: ``CONFIG_CGROUPS``, ``CONFIG_CGROUP_CPUACCT``, ``CONFIG_MEMCG`` (previously called as ``CONFIG_CGROUP_MEM_RES_CTLR``), ``CONFIG_CPUSETS``, ``CONFIG_PID_NS``, ``CONFIG_IPC_NS``, ``CONFIG_NET_NS``. It is anyway suggested to use Linux kernel version at least 3.8.

Then you require the compilation and execution environments for the languages you will use in your contest:

* `GNU compiler collection <https://gcc.gnu.org/>`_ (for C, C++ and Java, respectively with executables ``gcc``, ``g++`` and ``gcj``);

* `Free Pascal <http://www.freepascal.org/>`_ (for Pascal, with executable ``fpc``);

* `Python <http://www.python.org/>`_ >= 2.7, < 3.0 (for Python, with executable ``python2``; note though that this must be installed anyway because it is required by CMS itself);

* `PHP <http://www.php.net>`_ >= 5 (for PHP, with executable ``php5``).

All dependencies can be installed automatically on most Linux distributions.

Ubuntu
------

On Ubuntu 14.04, one will need to run the following script to satisfy all dependencies:

.. sourcecode:: bash

    sudo apt-get install build-essential fpc postgresql postgresql-client \
         gettext python2.7 iso-codes shared-mime-info stl-manual cgroup-lite

    # Only if you will use pip/virtualenv to install python dependencies
    sudo apt-get install python-dev libpq-dev libcups2-dev libyaml-dev

    # Optional
    sudo apt-get install nginx-full php5-cli php5-fpm phppgadmin \
         texlive-latex-base a2ps

Arch Linux
----------

On Arch Linux, unofficial AUR packages can be found: `cms <http://aur.archlinux.org/packages/cms>`_ or `cms-git <http://aur.archlinux.org/packages/cms-git>`_. However, if you do not want to use them, the following command will install almost all dependencies (some of them can be found in the AUR):

.. sourcecode:: bash

    sudo pacman -S base-devel fpc postgresql postgresql-client python2 \
         iso-codes shared-mime-info

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/libcgroup/
    # https://aur.archlinux.org/packages/sgi-stl-doc/

    # Only if you will use pip/virtualenv to install python dependencies
    sudo pacman -S postgresql-libs libcups libyaml

    # Optional
    sudo pacman -S nginx php php-fpm phppgadmin texlive-core a2ps

Debian
------

While Debian uses (almost) the same packages as Ubuntu, setting up cgroups is more involved.
Debian requires the memory module of cgroups to be activated via a kernel command line parameter. Add ``cgroup_enable=memory`` to ``GRUB_CMDLINE_LINUX_DEFAULT`` in ``/etc/default/grub`` and then run ``update-grub``.

Also, we need to mount the cgroup filesystems (under Ubuntu, the cgroup-lite package does this). To do this automatically, add the following file into /etc/init.d:

.. sourcecode:: bash

    #! /bin/sh
    # /etc/init.d/cgroup

    # The following part carries out specific functions depending on arguments.
    case "$1" in
      start)
        mount -t tmpfs none /sys/fs/cgroup/
        mkdir /sys/fs/cgroup/memory
        mount -t cgroup none /sys/fs/cgroup/memory -o memory
        mkdir /sys/fs/cgroup/cpuacct
        mount -t cgroup none /sys/fs/cgroup/cpuacct -o cpuacct
        mkdir /sys/fs/cgroup/cpuset
        mount -t cgroup none /sys/fs/cgroup/cpuset -o cpuset
        ;;
      stop)
        umount /sys/fs/cgroup/cpuset
        umount /sys/fs/cgroup/cpuacct
        umount /sys/fs/cgroup/memory
        umount /sys/fs/cgroup
        ;;
      *)
        echo "Usage: /etc/init.d/foobar {start|stop}"
        exit 1
        ;;
    esac

    exit 0

Then execute ``chmod 755 /etc/init.d/cgroup`` as root and finally ``update-rc.d cgroup defaults`` to add the script to the default scripts.
The following command should now mount the cgroup filesystem:

.. sourcecode:: bash

    /etc/init.d/cgroup start


Python dependencies
===================

These are all the python dependencies required to run CMS:

.. literalinclude:: ../requirements.txt
   :language: python

These are all the python dependencies required to develop CMS:

.. literalinclude:: ../dev-requirements.txt
   :language: python

There are good reasons to install Python dependencies via pip (Python Package Index) instead of your package manager, for example: two different Linux distributions may "offer" two different versions of ``python-sqlalchemy`` while, when using pip, you can choose to install a version that is known to be working correctly with CMS.

The easy way of installing Python dependencies, assuming you have ``pip`` installed, is this:

.. sourcecode:: bash

    pip install --user -r requirements.txt

This command installs python dependencies in your home folder. If you really want to install them globally then you should remove ``--user`` and run the install command as root (but, depending on your distribution, this might be a bad idea as it might interfere with the system package manager).

There are other ways to manage python dependencies:

virtualenv
----------

A `virtual environment <https://virtualenv.pypa.io/en/latest/>`_ is an isolated Python environment that you can put wherever you like and that can be "activated" and "deactivated" at will. The tool you need in order to create a virtual environment is called ``virtualenv``, and can be installed by looking for ``python-virtualenv`` using your Linux distribution's package manager. For example:

* Ubuntu: `python-virtualenv <https://apps.ubuntu.com/cat/applications/python-virtualenv/>`_.
* Arch Linux: `python-virtualenv <https://www.archlinux.org/packages/extra/any/python-virtualenv/>`_.

.. FUTURE FIXME: virtualenv installation is necessary only on python2; when the
   porting to python3 will be complete, the "new" way of creating a virtual
   environment will be ``pyvenv`` or equivalently ``python -m venv`` (the venv
   module and the pyvenv script come bundled with python3, so there is no need
   to install virtualenv anymore).

Once you installed ``virtualenv``, you will need to create a virtual environment somewhere in your filesystem. For example, let's assume that you decided to create it under your home directory (as ``~/cms_venv``):

.. sourcecode:: bash

    virtualenv -p python2 ~/cms_venv

To "activate" it:

.. sourcecode:: bash

    . ~/cms_venv/bin/activate

Or equivalently:

.. sourcecode:: bash

    source ~/cms_venv/bin/activate

After the activation, ``pip`` will *always* be available (even if it was not available globally, e.g. because you did not install it) and, in general, every python command (python, pip) will refer to their corresponding virtual version. So, you can install python dependencies by issuing:

.. sourcecode:: bash

    pip install -r requirements.txt

.. note::

    Once you finished installing CMS (and using it) you can deactivate the virtual environment by issuing:

    .. sourcecode:: bash

        deactivate

Ubuntu
------

.. warning::

  It is usually possible to install python dependencies using your Linux distribution's package manager. However, keep in mind that the version of each package is controlled by the package mantainers and could be too new or too old for CMS. This is generally not the case on Ubuntu since we try to build on the python packages that are available for the current LTS version.

To install CMS python dependencies on Ubuntu, you can issue:

.. sourcecode:: bash

    sudo apt-get install python-setuptools python-tornado python-psycopg2 \
         python-sqlalchemy python-psutil python-netifaces python-crypto \
         python-tz python-six python-beautifulsoup python-mechanize \
         python-coverage python-mock python-requests python-werkzeug \
         python-gevent patool

    # Optional.
    # sudo apt-get install python-yaml python-sphinx python-cups python-pypdf2

Arch Linux
----------

.. warning::

  It is usually possible to install python dependencies using your Linux distribution's package manager. However, keep in mind that the version of each package is controlled by the package mantainers and could be too new or too old for CMS. This is especially true for Arch Linux, which is a bleeding edge distribution.

To install CMS python dependencies on Arch Linux (again: assuming you did not use the aforementioned AUR packages), you can issue:

.. sourcecode:: bash

    sudo pacman -S python2-setuptools python2-tornado python2-psycopg2 \
         python2-sqlalchemy python2-psutil python2-netifaces python2-crypto \
         python2-pytz python2-six python2-beautifulsoup3 python2-mechanize \
         python2-mock python2-requests python2-werkzeug python2-gevent \
         python2-coverage

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/patool/

    # Optional.
    # sudo pacman -S python2-yaml python-sphinx python2-pycups
    # Optionally install the following from AUR.
    # https://aur.archlinux.org/packages/python2-pypdf2/

Installing CMS
==============

You can download CMS |release| from :gh_download:`GitHub` and extract it on your filesystem. After that, you can install it (recommended, not necessary though):

.. sourcecode:: bash

    ./setup.py install --user

Or, if you prefer to use pip:

.. sourcecode:: bash

    pip install --user .

.. note::

    If you are going to use a virtual environment then you will not need the ``--user`` flag.

In order to run CMS there are some preparation steps to run (like installing the sandbox, compiling localization files, creating the ``cmsuser``, and so on). You can either do all these steps by hand or you can run the following command:

.. sourcecode:: bash

    sudo ./prerequisites.py install

Both commands will install CMS in your home folder. If you really want to install it globally then you should remove ``--user`` and run the install command as root (but, depending on your distribution, this might be a bad idea as it might interfere with the system package manager).

If you install CMS, you also need to add your user to the ``cmsuser`` group and logout to make the change effective:

.. sourcecode:: bash

    sudo usermod -a -G cmsuser <your user>

You can verify to be in the group by issuing the command:

.. sourcecode:: bash

    groups

.. warning::

   Users in the group ``cmsuser`` will be able to launch the ``isolate`` program with root permission. They may exploit this to gain root privileges. It is then imperative that no untrusted user is allowed in the group ``cmsuser``.

.. _installation_updatingcms:

Updating CMS
============

As CMS develops, the database schema it uses to represent its data may be updated and new versions may introduce changes that are incompatible with older versions.

To preserve the data stored on the database you need to dump it on the filesystem using ``cmsContestExporter`` **before you update CMS** (i.e. with the old version).

You can then update CMS and reset the database schema by running:

.. sourcecode:: bash

    cmsDropDB
    cmsInitDB

To load the previous data back into the database you can use ``cmsContestImporter``: it will adapt the data model automatically on-the-fly (you can use ``cmsDumpUpdater`` to store the updated version back on disk and speed up future imports).
