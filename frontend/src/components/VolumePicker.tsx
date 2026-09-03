/**
 * VolumePicker.tsx — choose an external volume as the offload destination.
 *
 * Offload (Phase 7) moves cold files/cohorts to an external disk. This picker
 * lists mounted external volumes (from api.listVolumes) and lets the user select
 * one; the selected volume's path becomes the offload dest_path. Presentation
 * only; App fetches volumes and owns the selection.
 */

import type { Volume } from "../types";

interface VolumePickerProps {
  volumes: Volume[];
  selectedPath: string | null;
  onSelect: (path: string) => void;
  onRefresh: () => void; // re-scan for drives (user just plugged one in)
}

export default function VolumePicker({ volumes, selectedPath, onSelect: onSelect, onRefresh: onRefresh }: VolumePickerProps) {
  if (volumes.length === 0) {
    return (
      <section className="volume-picker empty-state">
        <p>No external drives connected. Plug one in and refresh.</p>
        <button onClick={onRefresh}>Refresh Drives</button>
      </section>
    );
  }

  return (
    <section className="volume-picker">
      <h3>Offload destination</h3>
      <div className="picker-controls" style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
        <select 
          value={selectedPath || ""} 
          onChange={(e) => onSelect(e.target.value)}
        >
          <option value="" disabled>Select a drive...</option>
          {volumes.map((vol) => (
            <option key={vol.path} value={vol.path}>
              {vol.name} · {vol.free_human} free
            </option>
          ))}
        </select>
        
        <button onClick={onRefresh}>Refresh</button>
      </div>
    </section>
  );
}
