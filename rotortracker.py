Python 3.13.5 (tags/v3.13.5:6cb20a2, Jun 11 2025, 16:15:46) [MSC v.1943 64 bit (AMD64)] on win32
Enter "help" below or click "Help" above for more information.
import React, { useState, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import { CalendarIcon } from 'lucide-react';
import { format } from 'date-fns';

export default function PumpRotorTracker() {
  const [logData, setLogData] = useState([]);
  const [date, setDate] = useState(new Date());
  const [sizeMM, setSizeMM] = useState('');
  const [quantity, setQuantity] = useState('');
  const [type, setType] = useState('in');
  const [remarks, setRemarks] = useState('');

  const handleAddEntry = () => {
    if (!sizeMM || !quantity) return;
    const newEntry = {
      date: format(date, 'yyyy-MM-dd'),
      sizeMM,
      quantity: parseInt(quantity),
      type,
      remarks,
    };
    setLogData([...logData, newEntry]);
    setSizeMM('');
    setQuantity('');
    setType('in');
    setRemarks('');
  };

  const inventory = useMemo(() => {
    const inv = {};
    logData.forEach(entry => {
      if (!inv[entry.sizeMM]) inv[entry.sizeMM] = 0;
      inv[entry.sizeMM] += entry.type === 'in' ? entry.quantity : -entry.quantity;
    });
    return inv;
  }, [logData]);

  return (
    <div className="max-w-2xl mx-auto p-4 space-y-4">
      <Card>
        <CardContent className="space-y-4 p-4">
          <h1 className="text-xl font-bold">Submersible Pump Rotor Tracker</h1>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label>Date</label>
              <div className="flex items-center space-x-2">
                <Input
                  type="date"
                  value={format(date, 'yyyy-MM-dd')}
                  onChange={(e) => setDate(new Date(e.target.value))}
                />
                <CalendarIcon className="w-5 h-5" />
              </div>
            </div>
            <div>
              <label>Rotor Size (mm)</label>
              <Input
                type="number"
                value={sizeMM}
                onChange={(e) => setSizeMM(e.target.value)}
                placeholder="e.g., 32"
              />
            </div>
            <div>
              <label>Quantity</label>
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                placeholder="e.g., 10"
              />
            </div>
            <div>
              <label>Type</label>
              <select
                className="border rounded p-2 w-full"
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                <option value="in">IN</option>
                <option value="out">OUT</option>
              </select>
            </div>
            <div className="col-span-2">
              <label>Remarks</label>
              <Input
                type="text"
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Remarks if any"
              />
            </div>
          </div>
          <Button onClick={handleAddEntry}>Add Entry</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <h2 className="text-lg font-semibold mb-2">Log Entries</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Rotor Size (mm)</TableHead>
                <TableHead>Quantity</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Remarks</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center">
                    No entries yet.
                  </TableCell>
                </TableRow>
              ) : (
                logData.map((entry, index) => (
                  <TableRow key={index}>
                    <TableCell>{entry.date}</TableCell>
                    <TableCell>{entry.sizeMM} mm</TableCell>
                    <TableCell>{entry.quantity}</TableCell>
                    <TableCell className={entry.type === 'in' ? 'text-green-600' : 'text-red-600'}>
                      {entry.type.toUpperCase()}
                    </TableCell>
                    <TableCell>{entry.remarks}</TableCell>
                  </TableRow>
...                 ))
...               )}
...             </TableBody>
...           </Table>
...         </CardContent>
...       </Card>
... 
...       <Card>
...         <CardContent className="p-4">
...           <h2 className="text-lg font-semibold mb-2">Current Inventory</h2>
...           <Table>
...             <TableHeader>
...               <TableRow>
...                 <TableHead>Rotor Size (mm)</TableHead>
...                 <TableHead>Quantity Left</TableHead>
...               </TableRow>
...             </TableHeader>
...             <TableBody>
...               {Object.keys(inventory).length === 0 ? (
...                 <TableRow>
...                   <TableCell colSpan={2} className="text-center">No inventory yet.</TableCell>
...                 </TableRow>
...               ) : (
...                 Object.entries(inventory).map(([size, qty], index) => (
...                   <TableRow key={index}>
...                     <TableCell>{size} mm</TableCell>
...                     <TableCell className={qty >= 0 ? 'text-green-600' : 'text-red-600'}>{qty}</TableCell>
...                   </TableRow>
...                 ))
...               )}
...             </TableBody>
...           </Table>
...         </CardContent>
...       </Card>
...     </div>
...   );
... }
