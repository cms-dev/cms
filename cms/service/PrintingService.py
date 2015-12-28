#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2014 Stefano Maggiolo <s.maggiolo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""A service that prints files.

"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import cups
import json
import logging
import os
import subprocess
import tempfile
from tornado import template
from PyPDF2 import PdfFileReader, PdfFileMerger

from cms import config
from cms.db.filecacher import FileCacher
from cms.io import Executor, QueueItem, TriggeredService, rpc_method
from cms.io.GeventUtils import rmtree
from cms.db import SessionGen, PrintJob
from cms.server import format_datetime
from cmscommon.commands import pretty_print_cmdline
from cmscommon.datetime import get_timezone


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class PrintingOperation(QueueItem):
    def __init__(self, printjob_id):
        self.printjob_id = printjob_id

    def __str__(self):
        return "printing job %d" % self.printjob_id

    def to_dict(self):
        return {"printjob_id": self.printjob_id}


class PrintingExecutor(Executor):
    def __init__(self, file_cacher):
        super(PrintingExecutor, self).__init__()

        self.file_cacher = file_cacher
        template_dir = os.path.join(os.path.dirname(__file__),
                                    "templates", "printing")
        self.template_loader = template.Loader(template_dir, autoescape=None)

    def execute(self, entry):
        """Print a print job.

        This is the core of PrintingService.

        entry (QueueEntry): the entry containing the operation to
            perform.

        """
        # TODO: automatically re-enqueue in case of a recoverable
        # error.
        printjob_id = entry.item.printjob_id
        with SessionGen() as session:
            # Obtain print job.
            printjob = PrintJob.get_from_id(printjob_id, session)
            if printjob is None:
                raise ValueError("Print job %d not found in the database." %
                                 printjob_id)
            user = printjob.participation.user
            contest = user.contest
            timezone = get_timezone(contest, user)
            timestr = format_datetime(printjob.timestamp, timezone)
            filename = printjob.filename

            # Check if it's ready to be printed.
            if printjob.done:
                logger.info("Print job %d was already sent to the printer.",
                            printjob_id)

            directory = tempfile.mkdtemp(dir=config.temp_dir)
            logger.info("Preparing print job in directory %s", directory)

            # Take the base name just to be sure.
            relname = "source_" + os.path.basename(filename)
            source = os.path.join(directory, relname)
            with open(source, "wb") as file_:
                self.file_cacher.get_file_to_fobj(printjob.digest, file_)

            if filename.endswith(".pdf") and config.pdf_printing_allowed:
                source_pdf = source
            else:
                # Convert text to ps.
                source_ps = os.path.join(directory, "source.ps")
                cmd = ["a2ps",
                       source,
                       "--delegate=no",
                       "--output=" + source_ps,
                       "--medium=%s" % config.paper_size.capitalize(),
                       "--portrait",
                       "--columns=1",
                       "--rows=1",
                       "--pages=1-%d" % (config.max_pages_per_job),
                       "--header=",
                       "--footer=",
                       "--left-footer=",
                       "--right-footer=",
                       "--center-title=" + filename,
                       "--left-title=" + timestr]
                ret = subprocess.call(cmd, cwd=directory)
                if ret != 0:
                    raise Exception(
                        "Failed to convert text file to ps with command: %s"
                        "(error %d)" % (pretty_print_cmdline(cmd), ret))

                if not os.path.exists(source_ps):
                    logger.warning("Unable to convert from text to ps.")
                    printjob.done = True
                    printjob.status = json.dumps([
                        N_("Invalid file")])
                    session.commit()
                    rmtree(directory)
                    return

                # Convert ps to pdf
                source_pdf = os.path.join(directory, "source.pdf")
                cmd = ["ps2pdf",
                       "-sPAPERSIZE=%s" % config.paper_size.lower(),
                       source_ps]
                ret = subprocess.call(cmd, cwd=directory)
                if ret != 0:
                    raise Exception(
                        "Failed to convert ps file to pdf with command: %s"
                        "(error %d)" % (pretty_print_cmdline(cmd), ret))

            # Find out number of pages
            with open(source_pdf, "rb") as file_:
                pdfreader = PdfFileReader(file_)
                page_count = pdfreader.getNumPages()

            logger.info("Preparing %d page(s) (plus the title page)",
                        page_count)

            if page_count > config.max_pages_per_job:
                logger.info("Too many pages.")
                printjob.done = True
                printjob.status = json.dumps([
                    N_("Print job has too many pages")])
                session.commit()
                rmtree(directory)
                return

            # Add the title page
            title_tex = os.path.join(directory, "title_page.tex")
            title_pdf = os.path.join(directory, "title_page.pdf")
            with open(title_tex, "w") as f:
                f.write(self.template_loader.load("title_page.tex")
                        .generate(user=user, filename=filename,
                                  timestr=timestr,
                                  page_count=page_count,
                                  paper_size=config.paper_size))
            cmd = ["pdflatex",
                   "-interaction",
                   "nonstopmode",
                   title_tex]
            ret = subprocess.call(cmd, cwd=directory)
            if ret != 0:
                raise Exception(
                    "Failed to create title page with command: %s"
                    "(error %d)" % (pretty_print_cmdline(cmd), ret))

            pdfmerger = PdfFileMerger()
            with open(title_pdf, "rb") as file_:
                pdfmerger.append(file_)
            with open(source_pdf, "rb") as file_:
                pdfmerger.append(file_)
            result = os.path.join(directory, "document.pdf")
            with open(result, "wb") as file_:
                pdfmerger.write(file_)

            try:
                printer_connection = cups.Connection()
                printer_connection.printFile(
                    config.printer, result,
                    "Printout %d" % printjob_id, {})
            except cups.IPPError as error:
                logger.error("Unable to print: `%s'.", error)
            else:
                printjob.done = True
                printjob.status = json.dumps([N_("Sent to printer")])
                session.commit()
            finally:
                rmtree(directory)


class PrintingService(TriggeredService):
    """A service that prepares print jobs and sends them to a printer.

    """

    def __init__(self, shard):
        """Initialize the PrintingService.

        """
        super(PrintingService, self).__init__(shard)

        self.file_cacher = FileCacher(self)

        self.add_executor(PrintingExecutor(self.file_cacher))
        self.start_sweeper(61.0)

        if config.printer is None:
            logger.info("Printing is disabled, so the PrintingService is "
                        "idle.")
            return

    def _missing_operations(self):
        """Enqueue unprinted print jobs.

        Obtain a list of all the print jobs in the database, check
        each of them to see if it's still unprinted and if so enqueue
        them.

        """
        counter = 0
        with SessionGen() as session:
            for printjob in session.query(PrintJob) \
                    .filter(PrintJob.done == False).all():  # noqa
                self.enqueue(PrintingOperation(printjob.id),
                             timestamp=printjob.timestamp)
                counter += 1
        return counter

    @rpc_method
    def new_printjob(self, printjob_id):
        """Schedule the given print job.

        Put it in the queue to have it printed, sooner or later.

        printjob_id (int): the id of the printjob.

        """
        self.enqueue(PrintingOperation(printjob_id))
