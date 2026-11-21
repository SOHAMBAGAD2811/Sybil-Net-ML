import path from 'path';
import fs from 'fs';
import { NextResponse } from 'next/server';

export async function GET() {
  try {
    const csvPath = path.join(process.cwd(), '..', 'data', 'processed', 'node_scores.csv');
    const raw = fs.readFileSync(csvPath, 'utf-8');
    const lines = raw.trim().split('\n');
    const headers = lines[0].split(',');

    const data = lines.slice(1).map((line) => {
      const vals = line.split(',');
      return {
        node_id: vals[0],
        predicted_label: parseInt(vals[1]),
        sybil_probability: parseFloat(vals[2]),
        classification: vals[3],
      };
    });

    // Stats
    const total = data.length;
    const sybils = data.filter((d) => d.predicted_label === 1).length;
    const humans = total - sybils;
    const avgSybilProb = data.reduce((s, d) => s + d.sybil_probability, 0) / total;

    return NextResponse.json({ data, stats: { total, sybils, humans, avgSybilProb } });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
