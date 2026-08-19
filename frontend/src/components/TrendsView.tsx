/**
 * TrendsView.tsx — free-space-over-time chart.
 *
 * Given the disk-history points (one per completed scan), render a line chart of
 * FREE DISK SPACE over scan history — the "am I trending toward a full disk?"
 * story that fits the monitoring product (DESIGN.md §5). Presentation only; data
 * is fetched in App and passed in as props.
 *
 * Note: this plots free space (disk_free_bytes), NOT scanned-folder size. The
 * scanned-size series (scan_trends) still exists in the backend but is not shown.
 */
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid
} from "recharts";
import type { DiskHistoryPoint } from "../types";
import { formatBytes } from "../utils";

interface TrendsViewProps {
  points: DiskHistoryPoint[];
}

export default function TrendsView({ points }: TrendsViewProps) {
  // handle empty states
  if (points.length === 0) {
    return (
      <section className="trends-panel empty-state">
        <p>No scan history yet. Run a scan to start tracking free space.</p>
      </section>
    );
  }

  if (points.length === 1) {
    return (
      <section className="trends-panel empty-state">
        <p>Come back after another scan to see how your free space is trending.</p>
      </section>
    );
  }

  const formatTime = (epochSecs: number) => {
    return new Date(epochSecs * 1000).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const point = payload[0].payload as DiskHistoryPoint;
      return (
        <div className="chart-tooltip" style={{
          background: 'white',
          padding: '0.75rem',
          border: '1px solid #e0e0e0',
          borderRadius: '6px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
        }}>
          <p style={{ margin: '0 0 0.25rem 0', fontWeight: 600, color: '#666' }}>
            {formatTime(point.started_at)}
          </p>
          <p style={{ margin: 0, fontSize: '1.1rem', fontWeight: 'bold' }}>
            {point.free_human} free
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <section className="trends-panel" style={{ height: 320, marginBottom: '2rem' }}>
      <h2 style={{ marginBottom: '1rem' }}>Free Space Over Time</h2>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 10, right: 20, left: 10, bottom: 0 }}>
          {/* Subtle grid lines help readability without cluttering */}
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />

          <XAxis
            dataKey="started_at"
            tickFormatter={formatTime}
            tick={{ fill: '#666', fontSize: 12 }}
            tickLine={false}
            axisLine={{ stroke: '#ccc' }}
            minTickGap={30}
          />

          <YAxis
            dataKey="disk_free_bytes"
            tickFormatter={formatBytes}
            tick={{ fill: '#666', fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={70}
            // Start from 0 so the visual proportion of free space is accurate
            domain={[0, 'auto']}
          />

          <Tooltip content={<CustomTooltip />} />

          <Line
            type="monotone"
            dataKey="disk_free_bytes"
            stroke="#007aff" /* Standard accessible blue */
            strokeWidth={3}
            dot={{ r: 4, fill: "#007aff", strokeWidth: 0 }}
            activeDot={{ r: 7, stroke: "white", strokeWidth: 2 }}
            animationDuration={500}
          />
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}
