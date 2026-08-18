import { useState } from 'react'
import * as api from '../api'

// Named defect list with one-click dismissal and an inline magnified crop.
//
// Two decisions here are load-bearing:
//
//  - Dismissing is a single button, never a form. An operator who must fill in
//    a reason to clear a false call stops clearing them and starts ignoring the
//    station, which is the failure NFR-005 exists to prevent.
//  - Dismissed rows stay visible, greyed, rather than disappearing. The
//    inspection record is append-only, and the screen should reflect that: a
//    dismissal is a judgement someone made, not an erasure.
export default function DefectList({ result, onOverride, busy }) {
  const [openRegion, setOpenRegion] = useState(null)

  if (!result) {
    return <p className="empty">Run an inspection to see results.</p>
  }
  if (result.regions.length === 0) {
    return (
      <p className="empty">
        No deviations from the reference. Every inspected component matches the
        golden board.
      </p>
    )
  }

  return (
    <ul className="defect-list">
      {result.regions.map((region, index) => {
        const label = region.ref_des ?? `Region ${index + 1}`
        const isOpen = openRegion === region.id
        return (
          <li key={region.id ?? index} className={region.overridden ? 'dismissed' : ''}>
            <div className="defect-row">
              <button
                className="defect-main"
                onClick={() => setOpenRegion(isOpen ? null : region.id)}
                title="Show a magnified crop of this region"
              >
                <span className="defect-name">
                  {label}
                  {/* The class is what tells a rework technician what to do.
                      "C14 missing" is actionable; "C14 differs" is not. */}
                  {region.defect_class && region.defect_class !== 'present' && (
                    <span className={`defect-class class-${region.defect_class}`}>
                      {region.defect_class}
                    </span>
                  )}
                </span>
                <span className="defect-meta">
                  {region.area_px} px²
                  {region.confidence != null &&
                    ` · ${Math.round(region.confidence * 100)}% confidence`}
                  {/* An unnamed region means the change did not overlap any
                      known component -- worth saying, not hiding. */}
                  {!region.ref_des && ' · unmatched'}
                </span>
                {/* States what was measured, so the operator can judge the
                    call rather than take it on trust. */}
                {region.detail && <span className="defect-detail">{region.detail}</span>}
              </button>

              {region.overridden ? (
                <span className="dismissed-tag">dismissed</span>
              ) : (
                <button
                  className="override"
                  onClick={() => onOverride(region.id)}
                  disabled={busy}
                >
                  False call
                </button>
              )}
            </div>

            {isOpen && result.inspection_id != null && (
              <img
                className="defect-crop"
                src={api.regionCropUrl(result.inspection_id, region.id)}
                alt={`Magnified view of ${label}`}
              />
            )}
          </li>
        )
      })}
    </ul>
  )
}
