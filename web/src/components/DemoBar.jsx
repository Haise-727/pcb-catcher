// Demo-mode board picker.
//
// Stands in for physically swapping boards under the camera, so the whole
// defect range can be shown without hardware.
//
// The banner is deliberately loud. Demo mode serves synthetic frames, and
// anyone looking at the screen must be able to tell at a glance that this is
// not a live inspection -- a station quietly showing fake results would be
// far worse than one that is obviously a demo.
export default function DemoBar({ demo, onSelect, onSelectBench, busy }) {
  if (!demo) return null

  return (
    <div className="demo-bar">
      <div className="demo-label">
        <span className="demo-chip">DEMO MODE</span>
        <span className="demo-hint">
          Serving bundled board images through a simulated bench — no camera attached
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

      {/* Bench conditions. This row is what makes the hardware requirements
          demonstrable without hardware: switching to a degraded profile makes
          the stability gate fail and false calls appear on a good board, which
          is RSK-02's claim shown rather than asserted. */}
      {demo.bench_profiles?.length > 0 && (
        <div className="demo-bench">
          <span className="demo-bench-label">Bench conditions</span>
          <div className="demo-boards">
            {demo.bench_profiles.map((profile) => (
              <button
                key={profile.name}
                className={`demo-board ${profile.name === demo.bench_profile ? 'active' : ''} ${
                  profile.settings_locked ? '' : 'demo-board-degraded'
                }`}
                onClick={() => onSelectBench(profile.name)}
                disabled={busy}
                title={`${profile.description}\n\n${profile.expectation}`}
              >
                {profile.label}
              </button>
            ))}
          </div>
          <p className="demo-current">{demo.bench_expectation}</p>
        </div>
      )}
    </div>
  )
}
