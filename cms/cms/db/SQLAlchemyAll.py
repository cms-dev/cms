#!/usr/bin/python
# -*- coding: utf-8 -*-

# Programming contest management system
# Copyright © 2010-2011 Giovanni Mascellani <mascellani@poisson.phc.unipi.it>
# Copyright © 2010-2011 Stefano Maggiolo <s.maggiolo@gmail.com>
# Copyright © 2010-2011 Matteo Boscariol <boscarim@hotmail.com>
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

import sys

from sqlalchemy.orm import relationship, backref

from cms.db.SQLAlchemyUtils import db, Base, metadata, Session, SessionGen

from cms.db.Contest import Contest, Announcement
from cms.db.View import RankingView
from cms.db.User import User, Message, Question
from cms.db.Task import Task, Manager, Testcase, Attachment, PublicTestcase, SubmissionFormatElement
from cms.db.Submission import Submission, Token, Evaluation, File

# Last relationship configurations
def get_submissions(self, session):
    return session.query(Submission).join(Task).filter(Task.contest == self).all()
Contest.get_submissions = get_submissions

if __name__ == "__main__" and "redrop" in sys.argv[1:]:
    metadata.drop_all()

def main():
    metadata.create_all()
    session = Session()
    c = Contest.sample_contest()
    session.add(c)
    v = View.RankingView(c)
    #session.add(v)
    u = User.sample_user(c)
    #session.add(u)
    t = Task.sample_task(c)
    #session.add(t)
    v.set_score(View.Score(20.0, t, u))
    s = Submission.sample_submission(user=u, task=t)
    #session.add(s)
    s.play_token()
    session.flush()
    print "Submissions:"
    print c.get_submissions(session)
    session.commit()
    session.close()

if __name__ == "__main__":
    main()
