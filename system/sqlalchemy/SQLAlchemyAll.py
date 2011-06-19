#!/usr/bin/python

import sys

from SQLAlchemyUtils import *

import Contest
import View
import User

if __name__ == "__main__" and "redrop" in sys.argv[1:]:
    metadata.drop_all()
metadata.create_all()

if __name__ == "__main__":
    session = Session()
    c = Contest.sample_contest()
    session.add(c)
    v = View.RankingView(c)
    #session.add(v)
    u = User.sample_user(c)
    #session.add(u)
    session.flush()
    print c.id
    print v.id
    print u.id
    session.commit()
    session.close()
