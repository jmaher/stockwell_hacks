import os
import json
import glob
import sys

HIGH_FREQUENCY = 30
MEDIUM_FREQUENCY = 20

def parseData(filename):
    data = {}
    with open(filename, 'r') as f:
        data = json.load(f)

    bydate = {}
    total_pushes = 0
    for date in data['oranges']:
        if data['oranges'][date]['testruns'] == 0:
            continue
 
        bydate[date] = {'pushes': data['oranges'][date]['testruns'],
                        'failures': len(data['oranges'][date]['oranges']),
                        'orangefactor': 0}
        bydate[date]['orangefactor'] = bydate[date]['failures']*1.0 / bydate[date]['pushes']

    return bydate


files = ['0109.json', '0116.json', '0123.json', '0130.json',
         '0206.json', '0213.json', '0220.json', '0227.json',
         '0306.json', '0313.json', '0320.json', '0327.json']

counter = []
moving_average = 0
for file in list(glob.glob('2017/*.json')):
    data = parseData(file)
    dates = data.keys()
    dates.sort()
    for item in dates:
        counter.append(data[item]['orangefactor'])
        if len(counter) == 7:
            moving_average = sum(counter) / 7.0
            counter.remove(counter[0])
        print "%s,%s,%s,%.2f,%.2f" % (item, data[item]['pushes'], data[item]['failures'], data[item]['orangefactor'], moving_average)

