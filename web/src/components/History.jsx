// Recent inspection history.
//
// This is the traceability claim made visible: every board that passes through
// the station leaves a durable record. An MSME's current answer to "what did
// you check?" is a signature on a sheet, and this is the thing that replaces
// it -- so it belongs on screen, not only in the CSV export.
export default function History({ inspections, onSelect }) {
  if (!inspections.length) {
    return <p className="empty">No inspections recorded yet.</p>
  }

  return (
    <ul className="history-list">
      {inspections.map((entry) => (
        <li key={entry.id}>
          <button className="history-row" onClick={() => onSelect?.(entry.id)}>
            <span className={`history-verdict history-${entry.verdict}`}>
              {entry.verdict.toUpperCase()}
            </span>
            <span className="history-detail">
              <span className="history-id">#{entry.id}</span>
              <span className="history-time">
                {new Date(entry.started_at).toLocaleTimeString()}
              </span>
            </span>
            <span className="history-count">
              {entry.region_count} {entry.region_count === 1 ? 'region' : 'regions'}
            </span>
          </button>
        </li>
      ))}
    </ul>
  )
}
