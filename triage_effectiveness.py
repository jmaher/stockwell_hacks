import datetime
import time
import shelve
import requests
import json
import re

# download bug comments/history and figure out:
# resolution
# duration
# total stockwell instances
# duration of [stockwell]
# total needinfo's by sheriffs (TODO: define sheriffs)
# total triage comments by sheriffs
# array of time to answer sherriff:ni? in hours

def analyzeEmail(address):
    # determine if robot, sheriff, other
    retVal = address
    if address in ['automation@bmo.tld', 'intermittent-bug-filer@mozilla.bugs', 'orangefactor@bots.tld']:
        retVal = 'robot'
    if address in ['ryanvm@gmail.com', 'ccoroiu@mozilla.com', 'ebalazs@mozilla.com', 'nerli@mozilla.com',
                   'apavel@mozilla.com', 'csabou@mozilla.com', 'shindli@mozilla.com',
                   'jmaher@mozilla.com', 'gbrown@mozilla.com', 'aryx.bugmail@gmx-topmail.de']:
        retVal = 'sheriff'
    return retVal

def analyzeComment(comment, who):
    what = 'TBD'
    extra = ''

    # determine what action took place: filed, low_frequency, med_frequency, stockwell, duplicate, triage, resolved
    if comment.startswith('Filed by'):
        return 'opened', extra
    
    # low_frequency, med_frequency, stockwell
    ofre = re.compile('([0-9]+) failures in ([0-9]+) pushes.*')
    matches = ofre.match(comment)
    if matches:
        number = int(matches.group(1))
        if number < 20:
            return 'low_frequency', extra
        if number < 30:
            return 'med_frequency', extra
        if number > 30:
            return 'stockwell', extra

    if len(comment.split('marked as a duplicate of this bug')) > 1:
        return 'duplicate', extra

    if len(comment.split('This bug has been marked as a duplicate')) > 1:
        return 'closed', extra

    if who == 'sheriff':
        return 'triage', 'triage'

    if who != 'sheriff':
        return '', extra
    if who == 'sheriff':
        return '', extra

    print "unknown comment: %s" % comment
    return what, extra

def analyzeHistory(change, who):
    # TODO: doesn't deal with changing a value, only adding/removing
    action = 'removed'

    # often a change will change an existing field, not just add or remote
    if change['added'] != "":
        action = 'added'
    what = change[action]
    extra = ''

    if what.startswith('review'):
        return '', ''

    if what.startswith('needinfo'):
        extra = what.split('(')[-1]
        extra = extra.strip(')')
        if action == 'added':
            what = 'needinfo'
            if who == 'sheriff':
                what = 'triage'
        elif action == 'removed':
            what = 'responded'

    if change['field_name'] == 'whiteboard':
        if action == 'added' and len(what.split('stockwell')) > 1:
            extra = what.split('stockwell')[-1]
            extra = extra.split(']')[0]
            what = 'stockwell'
            if who == 'sheriff':
                what = 'triage'

    if change['field_name'] == 'resolution':
        what = 'opened'
        if action == 'added':
            what = 'closed'
            extra = change['added']

    if what == change[action]:
        print "unknown event: %s" % what
        print "unknown event: %s" % change

    return what, extra

def downloadBugInformation(bug_shelf, bugId):
    # https://bugzilla.mozilla.org/rest/bug/1464658/comment
    # https://bugzilla.mozilla.org/rest/bug/1464658/history

    if bugId in bug_shelf:
        bug_data = bug_shelf.get(bugId)
        return bug_data['history']

    url = "https://bugzilla.mozilla.org/rest/bug/%s/history" % bugId
    response = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
    data = response.json()
    if 'code' in data and data['code'] == 102:
        bug_shelf[bugId] = {'summary': 'private', 'history': []}
        return []
    history = data['bugs'][0]['history']

    url = "https://bugzilla.mozilla.org/rest/bug/%s/comment" % bugId
    response = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
    data = response.json()
    comments = data['bugs'][bugId]['comments']

    # merge comment/history into single array
    events = []

    for item in history:
        for change in item['changes']:
            # TODO: consider using field_name:keywords
            if change['field_name'] not in ['whiteboard', 'resolution', 'flagtypes.name']:
                continue
            who = analyzeEmail(item['who'])
            what, extra = analyzeHistory(change, who)
            events.append({'time': item['when'],
                           'timestamp': time.mktime(datetime.datetime.strptime(item['when'], '%Y-%m-%dT%H:%M:%SZ').timetuple()),
                           'author': who,
                           'text': '',
                           'extra': extra,
                           'what': what
                          })

    # for comments, we want: time, text, author
    for comment in comments:
        who = analyzeEmail(comment['author'])
        what, extra = analyzeComment(comment['text'], who)
        if not what and not extra:
            continue

        events.append({'time': comment['time'],
                       'timestamp': time.mktime(datetime.datetime.strptime(comment['time'], '%Y-%m-%dT%H:%M:%SZ').timetuple()),
                       'author': who,
                       'text': comment['text'],
                       'extra': extra,
                       'what': what})

    # sort events by time, post filter them (i.e. needinfo, whiteboard, cc, comment, etc.)
    def eventTime(elem):
        return elem['time']
    events.sort(key=eventTime, reverse=True)

    last_event = {'time': '', 'what': '', 'extra': ''}
    history = []
    eventLevels = {'opened': 0, 'duplicate': 0, 'low_frequency': 1, 'med_frequency': 2, 'stockwell': 3, 'needinfo': 4, 'triage': 7, 'responded': 7, 'closed': 7}
    for event in events:
        if debug >= 3:
            print "before: %s, %s, %s" % (event['time'], event['what'], event['extra'])
        if event['what'] == '':
            if debug >= 4:
                print("removing incoming event: %s" % event)
            continue
        # find all events in the same time and give it a common action keeping the most relevant event
        if event['time'] == last_event['time'] and \
           eventLevels[event['what']] >= eventLevels[last_event['what']]:
               if event['extra'] == '' and last_event['extra'] != '' or \
                  event['what'] in ['responded', 'triage'] and last_event['what'] == 'closed':
                   if debug >= 4:
                       print("skipping event: %s" % event)
                   continue
               if debug >= 4:
                   print("removing event: %s" % last_event)
               history.pop()

        # look at the neighboring events
        elif last_event['what'] != '' and eventLevels[event['what']] >= eventLevels[last_event['what']]:
          if debug >= 5:
              print("removing neighboring event: %s" % last_event)
          history.pop()

        last_event = event
        history.append(event)

    for event in history:
        if debug >= 2:
            print "final: %s, %s, %s" % (event['time'], event['what'], event['extra'])

    bug_shelf[bugId] = {'summary': 'TBD', 'history': history}
    return history

def parseResolution(bugData):
    retVal = "needswork"

    # look for item in history reverse ordered, for changing stockwell whiteboard tag
    return retVal

def parseDuration(bugData):
    retVal = []

    start = bugData[-1]['timestamp']
    end = bugData[0]['timestamp']
    stockwell = -1
    triage = []
    responded = bugData[0]['timestamp']
    state = ''
    for event in bugData:
        if event['what'] == 'opened':
            start = event['timestamp']
        if event['what'] == 'closed':
            end = event['timestamp']
            state = event['extra']
        if event['what'] == 'stockwell':
            stockwell = event['timestamp']
        if event['what'] == 'triage':
            triage.append(event['timestamp'])
        if event['what'] in ['responded', 'closed'] and event['timestamp'] < responded:
            responded = event['timestamp']
            if state == '':
                state = event['extra']

    if stockwell >= triage[-1]:
        stockwell = triage[-1]

    retVal.append((end - start) / 3600.0)
    retVal.append((stockwell - start) / 3600.0)
    retVal.append((triage[-1] - stockwell) / 3600.0)
    retVal.append((responded - triage[-1]) / 3600.0)
    retVal.append(state)

    if debug >= 2:
        print "total bug duration: %.2f hours" % (retVal[0])
        print "until stockwell duration: %.2f hours" % (retVal[1])
        print "stockwell to triage duration: %.2f hours" % (retVal[2])
        print "triage to respond duration: %.2f hours" % (retVal[3])
        print "bug status: %s" % retVal[4]

    # TODO: measuring multiple pings?
    # throw warning/error if >1 needswork change
    return retVal

def parseNeedinfo(bugData, sheriffs):
    retVal = []

    # parse changes for needinfo statements
    # store timestamps in array
    # ensure the 'who' field matches an email in sheriffs

    return len(retVal)


debug = 5
def main():
    global debug
    debug = 5
    bugs = [1464658, 1460552, 1456366]
#    bugs = [1391532]
    bug_shelf = shelve.open('bug_history.shelve', writeback = True)
    results = {}
    expected_results = {'1456366': [1526.8008333333332, 10.828611111111112, 0.0, 1515.9722222222222, 'INCOMPLETE'],
                        '1460552': [1136.37, 148.1638888888889, 0.0, 6.567777777777778, 'INCOMPLETE'],
                        '1464658': [869.7591666666667, 686.4916666666667, 119.06916666666666, 64.19833333333334, 'DUPLICATE']}
    for bug in bugs:
        data = downloadBugInformation(bug_shelf, str(bug))
        stats = parseDuration(data)
        print "%s: %s" % (bug, stats)
        if str(bug) not in expected_results.keys():
            print " * no expected results"
        elif expected_results[str(bug)] != stats:
            print " * expected: %s" % expected_results[str(bug)]
    bug_shelf.close()

main()