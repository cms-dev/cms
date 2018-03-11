.. _localization:

Localization
************

For developers
==============

When you change a string in a template or in a web server, you have to generate again the file :gh_blob:`cms/locale/cms.pot`. To do so, run this command from the root of the repository.

.. sourcecode:: bash

    ./setup.py extract_messages

When you have a new translation, or an update of an old translation, you need to update the ``cms.mo`` files (the compiled versions of the ``cms.po`` files). You can run ``python setup.py compile_catalog`` to update the ``cms.mo`` files for all translations (or add the ``-l <code>`` argument to update only the one for a given locale). The usual ``python setup.py install`` will do this automatically. Note that, to have the new strings, you need to restart the web server.


For translators
===============

To begin translating to a new language, run this command from the root of the repository.

.. sourcecode:: bash

    ./setup.py init_catalog -l <code>

Right after that, open the newly created :file:`cms/locale/<code>/LC_MESSAGES/cms.po` and fill the information in the header. To translate a string, simply fill the corresponding msgstr with the translations. You can also use specialized translation softwares such as poEdit and others.

When the developers update the ``cms.pot`` file, you do not need to start from scratch. Instead, you can create a new ``cms.po`` file that merges the old translated string with the new, to-be-translated ones. The command is the following, run inside the root of the repository.

.. sourcecode:: bash

    ./setup.py update_catalog -l <code>

After you are done translating the messages, please run the following command and check that no error messages are reported (the developers will be glad to assist you if any of them isn't clear):

.. sourcecode:: bash

    ./setup.py compile_catalog -l <code>
