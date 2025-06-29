import React, { useState, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from '@/components/ui/table';
import * as XLSX from 'xlsx';
import { format } from 'date-fns';

export default function RotorTrackerApp() {
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

  const handleExport = () => {
    const worksheet = XLSX.utils.json_to_sheet(logData);
    const workbook = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Rotor Log');
    XLSX.writeFile(workbook, 'rotor_log.xlsx');
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
        <CardContent className="space-y-3 p-4">
          <h1 className="text-xl font-bold">Rotor Accounting App</h1>
          <Input type="date" value={format(date, 'yyyy-MM-dd')} onChange={(e) => setDate(new Date(e.target.value))} />
          <Input type="number" placeholder="Rotor Size (mm)" value={sizeMM} onChange={(e) => setSizeMM(e.target.value)} />
          <Input type="number" placeholder="Quantity" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
          <select value={type} onChange={(e) => setType(e.target.value)} className="border rounded p-2">
            <option value="in">IN</option>
            <option value="out">OUT</option>
          </select>
          <Input type="text" placeholder="Remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
          <div className="flex gap-2">
            <Button onClick={handleAddEntry}>Add Entry</Button>
            <Button onClick={handleExport} variant="secondary">Export to Excel</Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <h2 className="text-lg font-semibold">Log Entries</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Size (mm)</TableHead>
                <TableHead>Qty</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Remarks</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logData.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-center">No entries yet.</TableCell>
                </TableRow>
              ) : (
                logData.map((entry, index) => (
                  <TableRow key={index}>
                    <TableCell>{entry.date}</TableCell>
                    <TableCell>{entry.sizeMM}</TableCell>
                    <TableCell>{entry.quantity}</TableCell>
                    <TableCell className={entry.type === 'in' ? 'text-green-600' : 'text-red-600'}>{entry.type.toUpperCase()}</TableCell>
                    <TableCell>{entry.remarks}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-4">
          <h2 className="text-lg font-semibold">Current Inventory</h2>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Size (mm)</TableHead>
                <TableHead>Qty Left</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {Object.keys(inventory).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={2} className="text-center">No inventory data.</TableCell>
                </TableRow>
              ) : (
                Object.entries(inventory).map(([size, qty], index) => (
                  <TableRow key={index}>
                    <TableCell>{size}</TableCell>
                    <TableCell className={qty >= 0 ? 'text-green-600' : 'text-red-600'}>{qty}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
