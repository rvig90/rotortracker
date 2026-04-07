import requests
import time
import xmltodict
import json

TALLY_URL = "http://127.0.0.1:9000"

XML_REQUEST = """
<ENVELOPE>
 <HEADER>
  <TALLYREQUEST>Export Data</TALLYREQUEST>
 </HEADER>
 <BODY>
  <EXPORTDATA>
   <REQUESTDESC>
    <REPORTNAME>Voucher Register</REPORTNAME>
    <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
        <VOUCHERTYPENAME>Sales</VOUCHERTYPENAME>
    </STATICVARIABLES>
   </REQUESTDESC>
  </EXPORTDATA>
 </BODY>
</ENVELOPE>
"""

def fetch():
    try:
        r = requests.post(TALLY_URL, data=XML_REQUEST)
        data = xmltodict.parse(r.text)

        with open("tally_cache.json", "w") as f:
            json.dump(data, f)

        print("✅ Synced Tally")
    except Exception as e:
        print("❌ Error:", e)

while True:
    fetch()
    time.sleep(120)  # every 2 mins
