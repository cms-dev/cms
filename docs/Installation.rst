Installation
************

.. _installation_dependencies:

Dependencies
============

These are our requirements (in particular we highlight those that are not usually installed by default) - previous versions may or may not work:

* build environment for the programming languages allowed in the competition;

* `PostgreSQL <http://www.postgresql.org/>`_ >= 9.0;

  .. We need 9.0 because of pg_largeobject_metadata (in drop_db).

* `GNU compiler collection <https://gcc.gnu.org/>`_ (in particular the C compiler ``gcc``);

* `gettext <http://www.gnu.org/software/gettext/>`_ >= 0.18;

* `Python <http://www.python.org/>`_ >= 2.7, < 3.0;

* `setuptools <http://pypi.python.org/pypi/setuptools>`_ >= 0.6;

* `Tornado <http://www.tornadoweb.org/>`_ >= 2.0;

* `Psycopg <http://initd.org/psycopg/>`_ >= 2.4;

* `gevent <http://www.gevent.org/>`_ >= 1.0;

* `SQLAlchemy <http://www.sqlalchemy.org/>`_ >= 0.7;

* `libcg <http://libcg.sourceforge.net/>`_;

* `psutil <https://code.google.com/p/psutil/>`_ >= 0.6;

  .. We need 0.6 because of the new memory API (https://code.google.com/p/psutil/wiki/Documentation#Memory).

* `netifaces <http://alastairs-place.net/projects/netifaces/>`_ >= 0.5;

* `PyCrypto <https://www.dlitz.net/software/pycrypto/>`_ >= 2.3;

* `pytz <http://pytz.sourceforge.net/>`_;

* `six <http://pythonhosted.org/six/>`_ >= 1.1;

* `requests <http://docs.python-requests.org/en/latest/>`_ >= 1.1;

* `werkzeug <http://werkzeug.pocoo.org/>`_ >= 0.8;

* `patool <http://wummel.github.io/patool>`_ >= 1.7;

* `iso-codes <http://pkg-isocodes.alioth.debian.org/>`_;

* `shared-mime-info <http://freedesktop.org/wiki/Software/shared-mime-info>`_;

* `PyYAML <http://pyyaml.org/wiki/PyYAML>`_ >= 3.10 (only for some importers);

* `BeautifulSoup <http://www.crummy.com/software/BeautifulSoup/>`_ >= 3.2 (only for running tests);

* `mechanize <http://wwwsearch.sourceforge.net/mechanize/>`_ >= 0.2 (only for running tests);

* `coverage <http://nedbatchelder.com/code/coverage/>`_ >= 3.4 (only for running tests);

* `mock <http://www.voidspace.org.uk/python/mock>`_ >= 1.0 (only for running tests);

* `Sphinx <http://sphinx-doc.org/>`_ (only for building documentation).

* `TeX Live <https://www.tug.org/texlive/>`_ (only for printing)

* `pycups <http://pypi.python.org/pypi/pycups>`_ (only for printing)

* `a2ps <https://www.gnu.org/software/a2ps/>`_ (only for printing)

* `PyPDF2 <https://pypi.python.org/pypi/PyPDF2>`_ (only for printing)

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
         gettext python2.7 python-setuptools python-tornado python-psycopg2 \
         python-sqlalchemy python-psutil python-netifaces python-crypto \
         python-tz python-six iso-codes shared-mime-info stl-manual \
         python-beautifulsoup python-mechanize python-coverage python-mock \
         cgroup-lite python-requests python-werkzeug python-gevent patool

    # Optional.
    # sudo apt-get install nginx-full php5-cli php5-fpm phppgadmin \
    #      python-yaml python-sphinx texlive-latex-base python-cups a2ps
    # You can install PyPDF2 using Python Package Index.

Arch Linux
----------

On Arch Linux, unofficial AUR packages can be found: `cms <http://aur.archlinux.org/packages/cms>`_ or `cms-git <http://aur.archlinux.org/packages/cms-git>`_. However, if you don't want to use them, the following command will install almost all dependencies (some of them can be found in the AUR):

.. sourcecode:: bash

    sudo pacman -S base-devel fpc postgresql postgresql-client python2 \
         setuptools python2-tornado python2-psycopg2 python2-sqlalchemy \
         python2-psutil python2-netifaces python2-crypto python2-pytz \
         python2-six iso-codes shared-mime-info python2-beautifulsoup3 \
         python2-mechanize python2-mock python2-requests python2-werkzeug \
         python2-gevent python2-coverage

    # Install the following from AUR.
    # https://aur.archlinux.org/packages/libcgroup/
    # https://aur.archlinux.org/packages/patool/
    # https://aur.archlinux.org/packages/sgi-stl-doc/

    # Optional.
    # sudo pacman -S nginx php php-fpm phppgadmin python2-yaml python-sphinx \
    #      texlive-core python2-pycups a2ps
    # Optionally install the following from AUR.
    # https://aur.archlinux.org/packages/python2-pypdf2/

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


Python dependencies via pip
---------------------------

If you prefer using Python Package Index, you can retrieve all Python dependencies with this line:

.. sourcecode:: bash

    sudo pip install -r REQUIREMENTS.txt


Installing CMS
==============

You can download CMS |release| from :gh_download:`GitHub` and extract it on your filesystem. After that, you can install it (recommended, not necessary though):

.. sourcecode:: bash

    ./setup.py build
    sudo ./setup.py install

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

