import Utils
import time

if __name__ == "__main__":
    try:
        c = Utils.ask_for_contest()
    except AttributeError as e:
        print "CouchDB server unavailable:", repr(e)
        exit(1)
    announcement = {
        "date": time.time(),
        "subject": raw_input("Write the subject: ")
        "text": raw_input("Write the text: ")
        }
    c.announcements.append(announcement)
    c.to_couch()
