import requests
import xmltodict
import json
import re

TALLY_URL = "http://<YOUR_VM_IP>:9000"

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

response = requests.post(TALLY_URL, data=XML_REQUEST)

raw_xml = response.text

# 🔥 CLEAN INVALID CHARACTERS
clean_xml = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;)', '&amp;', raw_xml)

# OPTIONAL: REMOVE NON-ASCII (extra safe)
clean_xml = clean_xml.encode("utf-8", "ignore").decode("utf-8")

# DEBUG (optional)
print(clean_xml[:1000])

data = xmltodict.parse(clean_xml)

with open("tally_cache.json", "w") as f:
    json.dump(data, f, indent=2)

print("✅ Data saved successfully")
