import Utils
import time

if __name__ == "__main__":
    try:
        c = Utils.ask_for_contest()
    except AttributeError as e:
        print "CouchDB server unavailable: "+repr(e)
        exit(1)
    announcement = dict()
    announcement["date"] = time.time()
    announcement["subject"] = raw_input("Write your announcement:")
    c.announcements.append(announcement)
    c.to_couch()
