import json

with open('bugs.json', 'r') as f:
    data = json.load(f)

for item in data['bugs']:
    print item
    break
    print "%s: %s: %s" % (item['id'], item['resolution'], item['last_change_time'])
