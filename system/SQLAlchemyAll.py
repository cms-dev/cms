#!/usr/bin/python

import sys

from SQLAlchemyUtils import *

import Contest
import View
import User
import Task
import Submission

if __name__ == "__main__" and "redrop" in sys.argv[1:]:
    metadata.drop_all()
metadata.create_all()

def main():
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
    print c.id
    print v.id
    print u.id
    print t.attachments["filename.txt"]
    session.commit()
    session.close()

if __name__ == "__main__":
    main()
