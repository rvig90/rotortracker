import requests
import json
import re

# 🔥 PUT YOUR VM IP HERE
TALLY_URL = "http://172.16.14.128:9000"   # <-- CHANGE THIS

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
        <EXPLODEFLAG>Yes</EXPLODEFLAG>
    </STATICVARIABLES>
   </REQUESTDESC>
  </EXPORTDATA>
 </BODY>
</ENVELOPE>
"""

response = requests.post(TALLY_URL, data=XML_REQUEST)
xml = response.text

# Extract vouchers safely
vouchers = re.findall(r"<VOUCHER.*?>.*?</VOUCHER>", xml, re.DOTALL)

data = []

for v in vouchers:
    try:
        vno = re.search(r"<VOUCHERNUMBER>(.*?)</VOUCHERNUMBER>", v)
        party = re.search(r"<PARTYLEDGERNAME>(.*?)</PARTYLEDGERNAME>", v)
        date = re.search(r"<DATE>(.*?)</DATE>", v)
        total = re.search(r"<AMOUNT>(.*?)</AMOUNT>", v)

        # 🔥 Extract items
        items = re.findall(r"<ALLINVENTORYENTRIES.*?>.*?</ALLINVENTORYENTRIES>", v, re.DOTALL)

        item_list = []

        for item in items:
            name = re.search(r"<STOCKITEMNAME>(.*?)</STOCKITEMNAME>", item)
            qty = re.search(r"<BILLEDQTY>(.*?)</BILLEDQTY>", item)
            rate = re.search(r"<RATE>(.*?)</RATE>", item)
            amt = re.search(r"<AMOUNT>(.*?)</AMOUNT>", item)
            desc = re.search(r"<BATCHALLOCATIONS.LIST>.*?<GODOWNNAME>(.*?)</GODOWNNAME>", item, re.DOTALL)

            item_list.append({
                "Item": name.group(1) if name else "",
                "Description": desc.group(1) if desc else "",
                "Qty": qty.group(1) if qty else "",
                "Rate": rate.group(1) if rate else "",
                "Amount": float(amt.group(1)) if amt else 0
            })

        data.append({
            "Voucher No": vno.group(1) if vno else "",
            "Party": party.group(1) if party else "",
            "Date": date.group(1) if date else "",
            "Total": float(total.group(1)) if total else 0,
            "Items": item_list
        })

    except:
        continue

# Save JSON
with open("tally_cache.json", "w") as f:
    json.dump(data, f, indent=2)

print("✅ Full invoice data saved")
