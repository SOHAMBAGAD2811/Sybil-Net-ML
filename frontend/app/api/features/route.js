import path from 'path';
import fs from 'fs';
import { NextResponse } from 'next/server';

export async function GET(request) {
  try {
    const { searchParams } = new URL(request.url);
    const wallet = searchParams.get('wallet');

    const csvPath = path.join(process.cwd(), '..', 'data', 'processed', 'features.csv');
    const raw = fs.readFileSync(csvPath, 'utf-8');
    const lines = raw.trim().split('\n');
    const headers = lines[0].split(',');

    const data = lines.slice(1).map((line) => {
      const vals = line.split(',');
      const obj = {};
      headers.forEach((h, i) => {
        obj[h] = isNaN(vals[i]) ? vals[i] : parseFloat(vals[i]);
      });
      return obj;
    });

    if (wallet) {
      const found = data.find((d) => d.node_id === wallet);
      if (!found) return NextResponse.json({ error: 'Wallet not found' }, { status: 404 });
      return NextResponse.json({ data: found });
    }

    // Return top 50 by pagerank for the leaderboard
    const sorted = data.sort((a, b) => b.pagerank - a.pagerank).slice(0, 50);
    return NextResponse.json({ data: sorted });
  } catch (err) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
