This is a local offline way for me to analyze some of the trends in high frequency intermittent failures.

The value here is the data, my code is typically hacks for me to parse and summarize the data- feel free to use it for examples of how to parse the data.

My data in here is found with a few queries:
wget -O bugs.json "https://bugzilla.mozilla.org/rest/bug?whiteboard=stockwell"
wget -O owner_triage.json "https://hg.mozilla.org/automation/orangefactor/raw-file/tip/owner_triage_components.json"
wget -O 0319.json "https://brasstacks.mozilla.com/orangefactor/api/bybug?startday=2018-03-12&endday=2018-03-19&tree=trunk"
mv 0319.json 2018/

then I edit prioritybugs.py to add 2018/0319.json to the list of files to process and run it:
python prioritybugs.py

dailycount.py is an example of bugs/per and easier to read for parsing the data.