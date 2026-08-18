// Recurring-defect view.
//
// This is what turns the station from a detector into something that improves
// the line. A single missing C14 is a rework job; C14 missing on 40% of boards
// is a feeder problem, and only the aggregate makes that visible.
//
// Rates matter more than counts here: "C14 failed 12 times" means nothing
// without knowing whether that was out of 15 boards or 1500, so every row
// carries its rate and the bar is scaled by it.
export default function Trends({ trends }) {
  if (!trends || !trends.designators.length) {
    return (
      <p className="empty">
        No recurring defects yet. Inspect a few boards and patterns will appear
        here.
      </p>
    )
  }

  const worst = trends.designators[0]?.rate || 1

  return (
    <div className="trends">
      <p className="trends-summary">
        Across <strong>{trends.inspections}</strong>{' '}
        {trends.inspections === 1 ? 'inspection' : 'inspections'}
      </p>

      <ul className="trend-list">
        {trends.designators.map((entry) => {
          // Scaled against the worst offender rather than 100%, so the shape of
          // the distribution stays readable when every rate is low.
          const width = Math.max((entry.rate / worst) * 100, 4)
          const classes = [
            entry.absent && `${entry.absent} absent`,
            entry.rotated && `${entry.rotated} rotated`,
            entry.offset && `${entry.offset} offset`,
          ].filter(Boolean)

          return (
            <li key={entry.ref_des}>
              <div className="trend-head">
                <span className="trend-name">{entry.ref_des}</span>
                <span className="trend-rate">
                  {Math.round(entry.rate * 100)}%
                  <span className="trend-count"> · {entry.occurrences}x</span>
                </span>
              </div>
              <div className="trend-bar">
                <div className="trend-fill" style={{ width: `${width}%` }} />
              </div>
              {classes.length > 0 && (
                <span className="trend-classes">{classes.join(' · ')}</span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
