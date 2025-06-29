import React, { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { motion } from 'framer-motion';

export default function RotorStockTracker() {
  const [entries, setEntries] = useState([]);
  const [form, setForm] = useState({ date: '', size: '', inward: '', outward: '', remarks: '' });

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const addEntry = () => {
    if (!form.date || !form.size) return;
    const newEntry = {
      ...form,
      inward: parseInt(form.inward || '0', 10),
      outward: parseInt(form.outward || '0', 10),
    };
    setEntries([...entries, newEntry]);
    setForm({ date: '', size: '', inward: '', outward: '', remarks: '' });
  };

  const calculateBalance = (size) => {
    const totalInward = entries.filter(e => e.size === size).reduce((sum, e) => sum + e.inward, 0);
    const totalOutward = entries.filter(e => e.size === size).reduce((sum, e) => sum + e.outward, 0);
    return totalInward - totalOutward;
  };

  const uniqueSizes = [...new Set(entries.map(e => e.size))];

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="p-4 max-w-3xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Submersible Pump Rotor Stock Tracker</h1>
      <Card className="mb-4">
        <CardContent className="grid grid-cols-2 md:grid-cols-6 gap-2 p-4">
          <Input type="date" name="date" value={form.date} onChange={handleChange} placeholder="Date" />
          <Input type="text" name="size" value={form.size} onChange={handleChange} placeholder="Size (mm)" />
          <Input type="number" name="inward" value={form.inward} onChange={handleChange} placeholder="Inward Qty" />
          <Input type="number" name="outward" value={form.outward} onChange={handleChange} placeholder="Outward Qty" />
          <Input type="text" name="remarks" value={form.remarks} onChange={handleChange} placeholder="Remarks" />
          <Button onClick={addEntry}>Add Entry</Button>
        </CardContent>
      </Card>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Size (mm)</TableHead>
            <TableHead>Inward Qty</TableHead>
            <TableHead>Outward Qty</TableHead>
            <TableHead>Balance Qty</TableHead>
            <TableHead>Remarks</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry, index) => (
            <TableRow key={index}>
              <TableCell>{entry.date}</TableCell>
              <TableCell>{entry.size}</TableCell>
              <TableCell>{entry.inward}</TableCell>
              <TableCell>{entry.outward}</TableCell>
              <TableCell>{calculateBalance(entry.size)}</TableCell>
              <TableCell>{entry.remarks}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Card className="mt-4">
        <CardContent className="p-4">
          <h2 className="text-xl font-semibold mb-2">Current Balance Summary</h2>
          <ul className="space-y-1">
            {uniqueSizes.map((size, idx) => (
              <li key={idx}>
                Size {size} mm: <strong>{calculateBalance(size)}</strong>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </motion.div>
  );
}
