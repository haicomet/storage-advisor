/**
 * DiskStatusBar.tsx — at-a-glance volume fullness + low-space flag.
 *
 * The always-visible header strip that makes the app feel like a monitor rather
 * than a one-shot report: how full the disk is right now, and a clear warning
 * when it's running low (DESIGN.md §5). Presentation only; App fetches the
 * status and passes it in.
 */

import type { DiskStatus } from "../types";
import { formatBytes } from "../utils";

interface DiskStatusBarProps {
  status: DiskStatus | null; // null before the first fetch
}

export default function DiskStatusBar({ status }: DiskStatusBarProps) {
  if (!status) {
    // TODO: render a quiet loading/placeholder strip ("Checking disk…").
    return (<section
              className="disk-status-bar"
              style={{
                padding: '1.25rem',
                backgroundColor: '#f8f9fa',
                borderRadius: '8px',
                marginBottom: '2rem',
                border: '1px solid #e0e0e0'
              }}
          >
              <span style={{ color: '#666', fontSize: '0.95rem' }}>Checking disk capacity…</span>
           </section>
    );
  }

  // formatting & dataviz math
  const { free_bytes, total_bytes, percent_free, is_low } = status;

  // meter showing used space, not free space
  const percentUsed = 100 - percent_free;
  const freeStr = formatBytes(free_bytes);
  const totalStr = formatBytes(total_bytes);

  // standard blue: normal, red: low-space warning
  const barColor = is_low ? "#d93025" : "#007aff";
  const bgColor = is_low ? "#fce8e6" : "#f8f9fa";
  const borderColor = is_low ? "#fad2cf" : "#e0e0e0";


  return (
    <section 
      className={`disk-status-bar${is_low ? " low" : ""}`}
      style={{
        padding: '1.25rem',
        backgroundColor: bgColor, 
        borderRadius: '8px', 
        marginBottom: '2rem',
        border: `1px solid ${borderColor}`
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '0.75rem' }}>
        <div style={{ fontSize: '1.05rem', color: '#202124' }}>
          <strong>{freeStr}</strong> free of {totalStr}
        </div>
        
        {is_low && (
          <div role="alert" style={{ color: '#d93025', fontWeight: 600, fontSize: '0.95rem' }}>
            ⚠️ Disk space running low
          </div>
        )}
      </div>

      {/* Accessible dataviz meter */}
      <div 
        role="meter" 
        aria-valuenow={percentUsed} 
        aria-valuemin={0} 
        aria-valuemax={100}
        aria-label="Disk usage"
        style={{ 
          height: '8px', 
          backgroundColor: '#e0e0e0', 
          borderRadius: '4px', 
          overflow: 'hidden',
          width: '100%' 
        }}
      >
        <div 
          style={{ 
            height: '100%', 
            width: `${percentUsed}%`, 
            backgroundColor: barColor,
            transition: 'width 0.5s ease-out' 
          }} 
        />
      </div>
    </section>
  );
}
