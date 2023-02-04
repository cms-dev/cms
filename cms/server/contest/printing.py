#!/usr/bin/env python3

# Contest Management System - http://cms-dev.github.io/
# Copyright © 2010-2014 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2015 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2012 Matteo Boscariol <boscarim@hotmail.com>
# Copyright © 2012-2018 Luca Wehrstedt <luca.wehrstedt@gmail.com>
# Copyright © 2013 Bernard Blackham <bernard@largestprime.net>
# Copyright © 2014 Artem Iglikov <artem.iglikov@gmail.com>
# Copyright © 2014 Fabian Gundlach <320pointsguy@gmail.com>
# Copyright © 2015-2016 William Di Luigi <williamdiluigi@gmail.com>
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

import logging

from sqlalchemy import func

from cms import config
from cms.db import PrintJob


logger = logging.getLogger(__name__)


# Dummy function to mark translatable strings.
def N_(msgid):
    return msgid


class PrintingDisabled(Exception):
    """Raised when printing is disabled."""

    pass


class UnacceptablePrintJob(Exception):
    """Raised when a printout request can't be accepted."""

    def __init__(self, subject, text, text_params=None):
        super().__init__(subject, text, text_params)
        self.subject = subject
        self.text = text
        self.text_params = text_params


def accept_print_job(sql_session, file_cacher, participation, timestamp, files):
    """Add a print job to the database.

    This function receives the values that a contestant provides to CWS
    when they request a printout, it validates them and, if there are
    no issues, stores the files and creates a PrintJob in the database.

    sql_session (Session): the SQLAlchemy database session to use.
    file_cacher (FileCacher): the file cacher to store the files.
    participation (Participation): the contestant who sent the request.
    timestamp (datetime): the moment at which the request occurred.
    files ({str: [HTTPFile]}): the provided files, as a dictionary
        whose keys are the field names and whose values are lists of
        Tornado HTTPFile objects (each with a filename and a body
        attribute). The expected format consists of one item, whose key
        is "file" and whose value is a singleton list.

    return (PrintJob): the PrintJob that was added to the database.

    raise (PrintingDisabled): if printing is disabled because there are
        no printers available).
    raise (UnacceptablePrintJob): if some of the requirements that have
        to be met in order for the request to be accepted don't hold.

    """

    if config.printer is None:
        raise PrintingDisabled()

    old_count = sql_session.query(func.count(PrintJob.id)) \
        .filter(PrintJob.participation == participation).scalar()
    if config.max_jobs_per_user <= old_count:
        raise UnacceptablePrintJob(
            N_("Too many print jobs!"),
            N_("You have reached the maximum limit of at most %d print jobs."),
            config.max_jobs_per_user)

    if len(files) != 1 or "file" not in files or len(files["file"]) != 1:
        raise UnacceptablePrintJob(
            N_("Invalid format!"),
            N_("Please select the correct files."))

    filename = files["file"][0].filename
    data = files["file"][0].body

    if len(data) > config.max_print_length:
        raise UnacceptablePrintJob(
            N_("File too big!"),
            N_("Each file must be at most %d bytes long."),
            config.max_print_length)

    try:
        digest = file_cacher.put_file_content(
            data, "Print job sent by %s at %s." % (participation.user.username,
                                                   timestamp))

    except Exception as error:
        logger.error("Storage failed! %s", error)
        raise UnacceptablePrintJob(
            N_("Print job storage failed!"),
            N_("Please try again."))

    # The file is stored, ready to submit!
    logger.info("File stored for print job sent by %s",
                participation.user.username)

    printjob = PrintJob(timestamp=timestamp,
                        participation=participation,
                        filename=filename,
                        digest=digest)
    sql_session.add(printjob)

    return printjob
