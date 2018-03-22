import os
import json
import glob
import sys

HIGH_FREQUENCY = 30
MEDIUM_FREQUENCY = 20

#TODO: refactor parseData to split by date and then merge/bucket per week
def parseDataByDate(filename):
    data = {}
    with open(filename, 'r') as f:
        data = json.load(f)

    if 'oranges' not in data:
        return {}

    bydate = {}
    total_pushes = 0
    mydata = {'oranges': {}}
    for date in data['oranges']:
        if data['oranges'][date]['testruns'] == 0:
            continue
 
        win10count = 0
        win10bugs = {}

        mydata['oranges'][date] = {'testruns': data['oranges'][date]['testruns'], 'oranges': [], 'orangecounter': 0}
        for iter in data['oranges'][date]['oranges']:
            try:
                summary = data['bugs'][iter['bug']]['summary']
                idx = summary.index('comparison')
                mydata['oranges'][date]['oranges'].append(iter)
            except:
                pass

            if iter['platform'] == 'windows10-64' and iter['branch'] == 'mozilla-inbound' and iter['buildtype'] == 'opt' and iter['bug'] != '1207900':
                win10count += 1
                if iter['bug'] not in win10bugs.keys():
                    win10bugs[iter['bug']] = 0
                win10bugs[iter['bug']] += 1

        day = date.split('-')[-1]
        day = int(day)
#        if date.startswith('2017-12') and day >= 15:
#            print("%s, %s" % (date, win10count))
#            for bug in win10bugs:
#                print(" %s, %s" % (bug, win10bugs[bug]))

        bydate[date] = {'pushes': mydata['oranges'][date]['testruns'],
                        'failures': len(mydata['oranges'][date]['oranges']),
                        'orangefactor': 0}
        bydate[date]['orangefactor'] = bydate[date]['failures']*1.0 / bydate[date]['pushes']

    return bydate


def parseData(filename):
    data = {}
    with open(filename, 'r') as f:
        data = json.load(f)

    if 'oranges' not in data:
        return {}

    bugcount = {}
    total_pushes = 0
    for date in data['oranges']:
        total_pushes += data['oranges'][date]['testruns']
        stars = data['oranges'][date]['oranges']
        for item in stars:
            try:
#                summary = data['bugs'][item['bug']]['summary']
#                idx = summary.index('comparison')
#                if item['platform'] != 'windows7-32':
#                    continue

                if item['bug'] not in bugcount:
                    bugcount[item['bug']] = 0
                bugcount[item['bug']] += 1

            except:
                pass

    priority = {}
    totals = {}
    total_oranges = 0
    high_oranges = 0
    for bugnumber in bugcount:
        if bugcount[bugnumber] >= MEDIUM_FREQUENCY:
            if bugnumber not in priority:
                priority[bugnumber] = bugcount[bugnumber]
                if bugcount[bugnumber] >= HIGH_FREQUENCY:
                    high_oranges += bugcount[bugnumber]
        total_oranges += bugcount[bugnumber]

    priority['high_oranges'] = high_oranges
    priority['pushes'] = total_pushes
    priority['all_of'] = (total_oranges * 1.0) / total_pushes
    priority['low_of'] = ((total_oranges - high_oranges) * 1.0) / total_pushes
    priority['all_oranges'] = total_oranges
    return priority

def mergePriority(old, new, verbose=False):
    repeat2 = 0
    repeat3 = 0
    repeat4 = 0

    # if new key, ensure we leave blanks (i.e. 0) for previous iterations
    if old == {}:
        prevlen = 0
        old['summary'] = []
        old['repeat2'] = []
        old['repeat3'] = []
        old['repeat4'] = []
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
        if validbug and new[item] >= HIGH_FREQUENCY:
            if old[item] and \
               old[item][-1] >= HIGH_FREQUENCY:
                repeat2 += 1
                if len(old[item]) > 1 and \
                   old[item][-2] >= HIGH_FREQUENCY:
                    repeat3 += 1
                    if len(old[item]) > 2 and \
                       old[item][-3] >= HIGH_FREQUENCY:
                        repeat4 += 1
        old[item].append(new[item])

    for item in old.keys():
        if len(old[item]) == prevlen:
            old[item].append(0)

    old['repeat2'].append(repeat2)
    old['repeat3'].append(repeat3)
    old['repeat4'].append(repeat4)
    return old

def parseBugzillaWhiteboards(filename):
    owners = []
    with open('owner_triage.json', 'r') as f:
        data = json.load(f)
    for item in data:
        component = "%s::%s" % (item[0], item[1])
        owners.append(component)
#        print component

    whiteboards = {}
    with open(filename, 'r') as f:
        data = json.load(f)

    status = ''
    productfix = 0
    testfix = 0
    fixed = 0
    infra = 0
    fixedreason = {}
    components = {}
    for item in data['bugs']:
        try:
            idx = item['summary'].index('image comparison')
        except:
            continue

        component = "%s::%s" % (item['product'], item['component'])
        if component not in components:
            components[component] = {'bugs': [], 'owner': '', 'fixed': 0, 'disabled': 0, 'infra': 0, 'needswork': 0, 'unknown': 0}
        components[component]['bugs'].append(item['id'])
        if component in owners:
            components[component]['owner'] = 'Yes'

        if 'disabled' in item['whiteboard']:
            status = 'disabled'
        elif 'fixed' in item['whiteboard']:
            status = 'fixed'
            fixed += 1
            if 'fixed:' in item['whiteboard']:
                reason = item['whiteboard'].split(':')[-1]
                reason = reason.split(']')[0]
                if reason not in fixedreason:
                    fixedreason[reason] = 0
                fixedreason[reason] += 1
                if 'fixed:product' in item['whiteboard']:
                    productfix += 1
                else:
                    testfix += 1

        elif 'infra' in item['whiteboard']:
            status = 'infra'
            infra += 1
        elif 'unknown' in item['whiteboard']:
            status = 'unknown'
        elif 'needswork' in item['whiteboard']:
            status = 'needswork'
        else:
            print "JMAHER: what: %s, %s" % (item['id'], item['whiteboard'])

        if status:
            whiteboards[str(item['id'])] = status
            components[component][status] += 1

    print "product fixes: %s" % productfix
    print "text fixes: %s" % testfix
    print "total fixed: %s" % fixed
    print "total infra: %s" % infra
    print fixedreason

#    print "\n\nComponents, Owner Triaged, Total Bugs, Total Fixed, Total Disabled"
#    for c in components:
#        print "%s, %s, %s, %s, %s" % (c, components[c]['owner'], len(components[c]['bugs']), components[c]['fixed'], components[c]['disabled'])
#    print "\n"

    return whiteboards

def summarizeStockwellBugs(files, verbose=False):
    whiteboards = parseBugzillaWhiteboards('bugs.json')

    priority = {}
    for file in files:
        priority = mergePriority(priority, parseData(file))

    bugs = priority.keys()
    bugs.sort()
    total_bugs = 0
    totals = {'infra': 0, 'needswork': 0, 'fixed': 0, 'disabled': 0, 'unknown': 0, 'TODO': 0}
    total_infra = 0
    total_failures = 0
    total_bugcount = 0
    for idx in bugs:
        whiteboard = 'TODO'
        if idx in whiteboards:
           whiteboard = whiteboards[idx]

        total_bugcount += sum(priority[idx])
        if whiteboard == 'infra':
            total_infra += sum(priority[idx])

        bug = priority[idx]
        try:
            bugnumber = int(idx)
        except:
            print "%s,%s, %s" % (idx, '', ','.join(["%.2f" % i for i in bug]))
            continue

        try:
            valid = False
            for x in bug:
                if int(x) >= HIGH_FREQUENCY:
                    valid = True

            if valid:
                if whiteboard=='TODO' or verbose:
                    print "%s,%s, %s" % (idx, whiteboard, ','.join([str(i) for i in bug]))
                total_bugs += 1
                totals[whiteboard] += 1
        except:
            print "ERROR: %s" % bug

    print "\ntotals:"
    print "bugs: %s" % total_bugs
    print "total infra: %s" % total_infra
    print "total bugs: %s" % total_bugcount
    for type in totals:
        print "%s: %s" % (type, totals[type])


def summarize200(files, verbose=False):
    whiteboards = parseBugzillaWhiteboards('bugs.json')

    MEDIUM_PRIORITY = 0
    priority = {}
    for file in files:
        priority = mergePriority(priority, parseData(file))
#        print parseData(file)

    found = []
#    for bug in whiteboards:
#        if whiteboards[bug] == 'disabled' and bug in priority and sum(priority[bug]) >= 200:
#            print "%s, %s - %s" % (bug, sum(priority[bug]), whiteboards[bug])


    policies = [{'total': 200, 'weeks': 4}, {'total': 150, 'weeks': 3}, {'total': 100, 'weeks': 3}]
    counter = 0
    found_bugs = {}
    for policy in policies:
      for bug in priority:
        if bug in ['summary', 'pushes', 'all_oranges', 'high_oranges', 'repeat2']:
            continue
        if sum(priority[bug]) >= policy['total']:
            idx = policy['weeks'] - 1
            while idx < len(priority[bug]):
                # Each idx is a 7 day window, so 4 weeks and 200
                start = idx - (policy['weeks'] - 1)
                if sum(priority[bug][start:idx]) >= policy['total']:
                    if bug not in found_bugs.keys():
                        found_bugs[bug] = []
                        for i in range(0, counter):
                            found_bugs[bug].append('')

                    if len(found_bugs[bug]) <= counter:
                        found_bugs[bug].append('1')
                idx += 1
      counter += 1
      for bug in found_bugs.keys():
          if len(found_bugs[bug]) != counter:
              found_bugs[bug].append('')

    # now determine the stockwell whiteboard tag
    for bug in found_bugs.keys():
#        try:
            print "%s: %s, %s: %s" % (bug, ','.join(found_bugs[bug]), sum(priority[bug]), whiteboards[bug])
#        except:
#            pass


def summarizeDailyStats(files):
    counter = []
    moving_average = 0
    for file in files:
        data = parseDataByDate(file)
        if data == {}:
            continue

        dates = data.keys()
        dates.sort()
        for item in dates:
            counter.append(data[item]['orangefactor'])
            if len(counter) == 7:
                moving_average = sum(counter) / 7.0
                counter.remove(counter[0])
#            print "%s,%s,%s,%.2f,%.2f" % (item, data[item]['pushes'], data[item]['failures'], data[item]['orangefactor'], moving_average)


#files = [f for f in list(glob.glob('2017/*.json'))]
files = [f for f in list(glob.glob('2018/*.json'))]

#summarizeDailyStats(files)
#print "\n"
summarizeStockwellBugs(files, verbose=False)
#summarize200(files)
