Localization
************

For developers
==============

When you change a string in a template or in a web server, you have to generate again the file :gh_blob:`cms/locale/cms.pot`. To do so, run this command from the root of the repository.

.. sourcecode:: bash

    xgettext -o cms/locale/cms.pot --language=Python --no-location \
      --keyword=_:1,2 --keyword=N_ --keyword=N_:1,2 --width=79 \
      cms/grading/*.py cms/grading/*/*.py cms/server/*.py \
      cms/server/contest/*.py cms/server/contest/handlers/*.py \
      cms/server/contest/templates/*.html

When you have a new translation, or an update of an old translation, you need to update the ``cms.mo`` files (the compiled versions of the ``cms.po`` files). You can run ``./prerequisites.py build_l10n`` to update all translations, and the usual ``python setup.py install`` to install them.

Alternatively, run the following inside the root of the repository.

.. sourcecode:: bash

    msgfmt cms/locale/<code>/LC_MESSAGES/cms.po -o cms/locale/<code>/LC_MESSAGES/cms.mo

And then copy the compiled ``.mo`` files to the appropriate folder. You may have to manually create the directory tree. Note that, to have the new strings, you need to restart the web server.


For translators
===============

To begin translating to a new language, run this command, from :gh_tree:`cms/locale/`.

.. sourcecode:: bash

    mkdir -p <two_letter_code_of_language>/LC_MESSAGES
    msginit --width=79 -l <two_letter_code_of_language>/LC_MESSAGES/cms

Right after that, open the newly created :file:`cms.po` and fill the information in the header. To translate a string, simply fill the corresponding msgstr with the translations. You can also use specialized translation softwares such as poEdit and others.

When the developers update the ``cms.pot`` file, you do not need to start from scratch. Instead, you can create a new ``cms.po`` file that merges the old translated string with the new, to-be-translated ones. The command is the following, run inside :gh_tree:`cms/locale/`.

.. sourcecode:: bash

    msgmerge --width=79 <code>/LC_MESSAGES/cms.po cms.pot > <code>/LC_MESSAGES/cms.new.po

You can now inspect the newly created :file:`cms.new.po` and, if you're satisfied, move it to :file:`cms.po` and finish the translation.
