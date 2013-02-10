Localization
************

For developers
==============

When you change a string in a template or in a web server, you have to generate again the file cms/server/po/messages.pot. To do so, use this command, from :file:`cms/server/`.

.. sourcecode:: bash

    xgettext -o po/messages.pot --language=Python --keyword=_:1,2 \
      \*.py \
      templates/admin/\*.html \
      templates/contest/\*.html

When you have a new translation, or an update of an old translation, you need to update the .mo files (the compiled versions of the .po). In the future we will have a beautiful setup script to handle this. In the meantime, run the following from :file:`cms/server/`.

.. sourcecode:: bash

    msgfmt po/<code>.po -o mo/<code>/LC_MESSAGES/cms.mo

If needed, create the tree. Note that to have the new strings, you need to restart the web server.


For translators
===============

To begin translating to a new language, run this command, from :file:`cms/server/po/`.

.. sourcecode:: bash

    msginit -d <two_letter_code_of_language>

Right after that, open :file:`<code>.po` and fill the information in the header. To translate a string, simply fill the corresponding msgstr with the translations.

If the developers updated the .pot file, you do not need to start from scratch. Instead, you can create a new .po that merges the old translated string with the new, to-be-translated ones. The command is the following, run from :file:`cms/server/po/`.

.. sourcecode:: bash

    msgmerge <code>.po messages.pot > <code>.po.new

You can now inspect :file:`<code>.po.new` and, if satisfyied, move it to :file:`<code>.po` and finish the translation.
