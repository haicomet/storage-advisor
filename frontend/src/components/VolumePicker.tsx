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

export default function VolumePicker({ volumes, selectedPath, onSelect: _onSelect, onRefresh: _onRefresh }: VolumePickerProps) {
  if (volumes.length === 0) {
    // TODO: "No external drives connected. Plug one in and Refresh." + a Refresh
    //   button wired to onRefresh (a drive may be connected after launch).
    return <section className="volume-picker empty-state" />;
  }

  // TODO: render
  //   - a selectable list/dropdown of volumes: name · free_human free
  //   - highlight the selectedPath; call onSelect(volume.path) on click
  //   - a Refresh control (onRefresh)
  //   - the selected volume is passed to api.offload as destPath. Whether a
  //     given cohort FITS is enforced at offload time (backend), but showing
  //     free_human here helps the user pick.
  return (
    <section className="volume-picker">
      <h3>Offload destination</h3>
      {/* TODO: volume list + selection + refresh */}
    </section>
  );
}
