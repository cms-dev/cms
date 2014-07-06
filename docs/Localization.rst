Localization
************

For developers
==============

When you change a string in a template or in a web server, you have to generate again the file :gh_blob:`cms/server/po/messages.pot`. To do so, run this command from the root of the repository.

.. sourcecode:: bash

    xgettext -o cms/server/po/messages.pot --language=Python --no-location \
      --keyword=_:1,2 --keyword=N_ --keyword=N_:1,2 --width=79 \
      cms/grading/*.py cms/grading/*/*.py cms/server/*.py \
      cms/server/templates/admin/*.html \
      cms/server/templates/contest/*.html

When you have a new translation, or an update of an old translation, you need to update the ``.mo`` files (the compiled versions of the ``.po`` files). You can run ``./setup.py build`` to update all translations (and also do a couple of other things, like compiling the sandbox). Alternatively, run the following inside :gh_tree:`cms/server/`.

.. sourcecode:: bash

    msgfmt po/<code>.po -o mo/<code>/LC_MESSAGES/cms.mo

If needed, create the tree. Note that to have the new strings, you need to restart the web server.


For translators
===============

To begin translating to a new language, run this command, from :gh_tree:`cms/server/po/`.

.. sourcecode:: bash

    msginit --width=79 -l <two_letter_code_of_language>

Right after that, open :file:`<code>.po` and fill the information in the header. To translate a string, simply fill the corresponding msgstr with the translations. You can also use specialized translation softwares such as poEdit and others.

When the developers update the ``.pot`` file, you do not need to start from scratch. Instead, you can create a new ``.po`` file that merges the old translated string with the new, to-be-translated ones. The command is the following, run inside :gh_tree:`cms/server/po/`.

.. sourcecode:: bash

    msgmerge --width=79 <code>.po messages.pot > <code>.new.po

You can now inspect :file:`<code>.new.po` and, if satisfied, move it to :file:`<code>.po` and finish the translation.
