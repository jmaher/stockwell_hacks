import os
import json
import glob
import sys
import shelve
import requests

from datetime import timedelta, datetime

HIGH_FREQUENCY = 0
MEDIUM_FREQUENCY = 0

def parseData(filename):
    data = {}
    with open(filename, 'r') as f:
        data = json.load(f)

    if 'oranges' not in data:
        return {}


    bugs = {}
    with open('tvbf_bugs.json', 'r') as f:
        bugdata = json.load(f)
    for item in bugdata['bugs']:
        bugs[str(item['id'])] = item

    bugcount = {}
    for date in data['oranges']:
        stars = data['oranges'][date]['oranges']
        for item in stars:
            try:
                if item['bug'] not in bugcount:
                    bugcount[item['bug']] = 0
                bugcount[item['bug']] += 1
            except Exception, e:
                print "ERROR: %s, %s" % (e, dir)
                pass

    priority = {}
    for bugnumber in bugcount:
        if bugcount[bugnumber] >= 0:
            if bugnumber not in priority:
                priority[bugnumber] = bugcount[bugnumber]

    return priority

def mergePriority(old, new, verbose=False):

    # if new key, ensure we leave blanks (i.e. 0) for previous iterations
    if old == {}:
        prevlen = 0
        old['summary'] = []
    else:
        prevlen = len(old[old.keys()[0]])

    count = 0
    for bug in new:
        try:
            x = int(bug)
            if int(new[bug]) >= HIGH_FREQUENCY:
                count += 1
        except:
            continue

    old['summary'].append(count)
    for item in new:
        validbug = False
        try:
            validbug = int(item)
            validbug = True
        except:
            # not a valid bug number
            pass

        if item not in old:
            old[item] = []
            for i in range(prevlen):
                old[item].append(0)
            if len(old[item]) != prevlen:
                print "ERROR"
        old[item].append(new[item])

    for item in old.keys():
        if len(old[item]) == prevlen:
            old[item].append(0)

    return old

def parseBugzillaWhiteboards(filename):
    whiteboards = {}
    with open(filename, 'r') as f:
        data = json.load(f)

    status = ''
    summaries = {}
    statuses = {}
    for item in data['bugs']:
        summaries[item['id']] = item['summary']
        statuses[str(item['id'])] = item['status'] + '-' + item['resolution']

        if 'pass:pass' in item['whiteboard']:
            status = 'pass'
        elif 'notfound' in item['whiteboard']:
            status = 'notfound'
        elif 'fail:fail' in item['whiteboard']:
            status = 'permafail'
        elif 'knownfail' in item['whiteboard']:
            status = 'knownfail'
        elif 'pass:fail' in item['whiteboard']:
            status = 'found'
        else:
            print "JMAHER: what: %s, %s" % (item['id'], item['whiteboard'])

        if status:
            whiteboards[str(item['id'])] = status

    return whiteboards, summaries, statuses

def summarizeStockwellBugs(db, verbose=False):
    whiteboards, summaries, statuses = parseBugzillaWhiteboards('tvbf_bugs.json')
    wb_bugs = whiteboards.keys()
    wb_bugs.sort()

    total = 0
    found_bugs = 0
    for bug in wb_bugs:
        count = []
        for startday in ['2018-07-05', '2018-07-12', '2018-07-19', '2018-07-26']:
            # https://treeherder.mozilla.org/api/failuresbybug/?startday=2018-07-01&endday=2018-07-19&tree=trunk&bug=1470757&format=json
            endday = datetime.strptime(startday, '%Y-%m-%d') + timedelta(days=7)
            endday = endday.strftime('%Y-%m-%d')
            url = 'https://treeherder.mozilla.org/api/failuresbybug/?startday=%s&endday=%s&tree=trunk&bug=%s&format=json' % (startday, endday, bug)
            data = db.get(url, {})
            if not data:
                print(url)
                response = requests.get(url, headers={'User-agent': 'Mozilla/5.0'})
                data = response.json()
                print data
                db[url] = data
            count.append(str(data['count']))
#        print("%s,%s" % (bug, ','.join(count)))
        print("%s,%s,%s,%s" % (bug, whiteboards[bug], statuses[bug], ','.join(count)))

db = shelve.open('tvbugs.shelve', writeback=True)
summarizeStockwellBugs(db)
db.close()