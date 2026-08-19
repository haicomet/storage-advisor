/**
 * ResultsTable.tsx — the ranked "Large & Stale" list with evidence.
 *
 * Given a list of FileRow items, render a table: path, human size, and the
 * evidence string, plus a "Reveal in Finder" action per row. This is the
 * product's payoff view — the transparent evidence is what earns user trust
 * (DESIGN.md §2/§8), so render `evidence` prominently, not as an afterthought.
 */

import type { FileRow } from "../types";
import { revealInFinder } from "../api";

interface ResultsTableProps {
  items: FileRow[];
  hasScanned: boolean;
}

export default function ResultsTable({ items, hasScanned }: ResultsTableProps) {

  if (items.length === 0) {
    return (
      <section className="empty-state success">
        <p>Scan complete! No files found matching the "Large & Stale" criteria.</p>
      </section>
    );
  }

  return (
    <section className="results-panel">
      <h2>Large & Stale Files ({items.length})</h2>
      <table>
        <thead>
          <tr>
            <th>Size</th>
            <th>File</th>
            <th>Evidence</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i}>
              <td className="bold">{item.size_human}</td>
              
              <td className="path-truncate" title={item.filepath}>
                {item.filepath.split('/').pop()}
              </td>
              
              <td className="evidence-col">{item.evidence}</td>
              
              <td>
                <button 
                  onClick={async () => {
                    try {
                      console.log("Attempting to reveal:", item.filepath);
                      await revealInFinder(item.filepath);
                    } catch (err) {
                      alert(`Could not reveal file:\n${err}`);
                    }
                  }}
                >
                  Reveal
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
