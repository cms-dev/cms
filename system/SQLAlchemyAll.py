#!/usr/bin/python

import sys

from sqlalchemy.orm import relationship, backref

from SQLAlchemyUtils import *

import Contest
import View
import User
import Task
import Submission

# Last relationship configurations
def get_submissions(self, session):
    return session.query(Submission.Submission).join(Task.Task).filter(Task.Task.contest == self).all()
Contest.Contest.get_submissions = get_submissions

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
