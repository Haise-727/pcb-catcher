// The single most important thing on screen.
//
// An operator glances at this between boards, often from half a metre back
// while still holding the next one. It has to be readable at that distance
// and unambiguous in under a second, which is why the word is oversized and
// never carries meaning by colour alone (NFR-008).
export default function VerdictCard({ result, activeCount }) {
  if (!result) {
    return (
      <div className="verdict verdict-idle">
        <span className="verdict-word">READY</span>
        <span className="verdict-meta">Place a board and press Inspect</span>
      </div>
    )
  }

  const passed = result.verdict === 'pass'
  const pathLabel =
    result.path_used === 'cad' ? 'CAD-referenced' : 'golden differencing'

  return (
    <div className={`verdict verdict-${result.verdict}`}>
      <div className="verdict-head">
        <span className="verdict-word">{passed ? 'PASS' : 'FAIL'}</span>
        <span className="verdict-mark" aria-hidden="true">
          {passed ? '✓' : '✕'}
        </span>
      </div>
      <span className="verdict-meta">
        {passed
          ? 'No deviations from the reference'
          : `${activeCount} active ${activeCount === 1 ? 'defect' : 'defects'}`}
      </span>
      <div className="verdict-tags">
        <span className="tag">{pathLabel}</span>
        {result.registration_residual_px != null && (
          // Registration error propagates into every region, so the operator
          // is shown it rather than it staying an internal diagnostic.
          <span className="tag">
            residual {result.registration_residual_px.toFixed(2)}px
          </span>
        )}
        {result.degraded && <span className="tag tag-warn">degraded</span>}
      </div>
    </div>
  )
}
