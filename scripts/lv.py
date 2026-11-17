#!/usr/bin/env python3
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:9090/object_info/LoadVideo", timeout=30))
print(json.dumps(d["LoadVideo"]["input"]["required"]["file"])[:800])
