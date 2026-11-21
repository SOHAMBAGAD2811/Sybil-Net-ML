import path from 'path';
import fs from 'fs';
import { NextResponse } from 'next/server';

const ALERTS_PATH = path.join(process.cwd(), '..', 'data', 'processed', 'mempool_alerts.json');

// GET /api/mempool — returns current alerts snapshot
export async function GET() {
  try {
    if (!fs.existsSync(ALERTS_PATH)) {
      return NextResponse.json({ alerts: [], running: false });
    }
    const raw = fs.readFileSync(ALERTS_PATH, 'utf-8');
    const alerts = JSON.parse(raw);
    return NextResponse.json({ alerts, running: true });
  } catch (err) {
    return NextResponse.json({ alerts: [], running: false, error: err.message });
  }
}
