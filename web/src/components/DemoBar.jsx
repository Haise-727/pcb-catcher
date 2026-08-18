// Demo-mode board picker.
//
// Stands in for physically swapping boards under the camera, so the whole
// defect range can be shown without hardware.
//
// The banner is deliberately loud. Demo mode serves synthetic frames, and
// anyone looking at the screen must be able to tell at a glance that this is
// not a live inspection -- a station quietly showing fake results would be
// far worse than one that is obviously a demo.
export default function DemoBar({ demo, onSelect, busy }) {
  if (!demo) return null

  return (
    <div className="demo-bar">
      <div className="demo-label">
        <span className="demo-chip">DEMO MODE</span>
        <span className="demo-hint">
          Serving bundled board images — no camera attached
        </span>
      </div>
      <div className="demo-boards">
        {demo.boards.map((board) => (
          <button
            key={board.index}
            className={`demo-board ${board.index === demo.board_index ? 'active' : ''}`}
            onClick={() => onSelect(board.index)}
            disabled={busy}
            title={board.description}
          >
            {board.name.replace('defect_', '').replace('golden', 'golden ✓')}
          </button>
        ))}
      </div>
      <p className="demo-current">{demo.board_description}</p>
    </div>
  )
}
