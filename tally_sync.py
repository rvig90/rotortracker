import requests
import json
import re

TALLY_URL = "http://172.16.14.128:9000"  # your VM IP

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
xml = response.text

# 🔥 Extract only required fields using regex (safe)
vouchers = re.findall(r"<VOUCHER.*?>.*?</VOUCHER>", xml, re.DOTALL)

data = []

for v in vouchers:
    try:
        date = re.search(r"<DATE>(.*?)</DATE>", v)
        party = re.search(r"<PARTYLEDGERNAME>(.*?)</PARTYLEDGERNAME>", v)
        vno = re.search(r"<VOUCHERNUMBER>(.*?)</VOUCHERNUMBER>", v)
        amount = re.search(r"<AMOUNT>(.*?)</AMOUNT>", v)

        data.append({
            "Date": date.group(1) if date else "",
            "Party": party.group(1) if party else "",
            "Voucher No": vno.group(1) if vno else "",
            "Amount": float(amount.group(1)) if amount else 0
        })

    except:
        continue  # skip bad entries

# Save clean JSON
with open("tally_cache.json", "w") as f:
    json.dump(data, f, indent=2)

print("✅ Clean data saved successfully")
