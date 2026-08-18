import { useEffect, useState } from 'react'
import * as api from '../api'

// Settings panel: live threshold tuning, storage, and the security posture.
//
// Three things worth showing rather than merely claiming:
//
//  - Thresholds are per board type and change at runtime (NFR-013). This is an
//    architectural driver, not a convenience -- it is why they live in a table
//    instead of as constants (ADR-004), and demonstrating a live retune is far
//    more convincing than saying it is possible.
//  - Storage is bounded and the sweep never touches inspection records.
//  - The station binds loopback only. Design files are the customer's
//    confidential IP and never leave the machine (NFR-011).
export default function Settings({ boardTypeId, busy, onNotice, onError }) {
  const [thresholds, setThresholds] = useState(null)
  const [storage, setStorage] = useState(null)
  const [draft, setDraft] = useState({})
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!boardTypeId) return
    api.getThresholds(boardTypeId).then((t) => {
      setThresholds(t)
      setDraft(t)
    }).catch(() => {})
  }, [boardTypeId])

  useEffect(() => {
    api.getStorage().then(setStorage).catch(() => {})
  }, [])

  const save = async () => {
    setSaving(true)
    try {
      const updated = await api.updateThresholds(boardTypeId, draft)
      setThresholds(updated)
      setDraft(updated)
      onNotice?.('Thresholds updated. They apply to the next inspection — no restart needed.')
    } catch (err) {
      onError?.(err.message)
    } finally {
      setSaving(false)
    }
  }

  const sweep = async () => {
    setSaving(true)
    try {
      const result = await api.sweepStorage()
      setStorage(await api.getStorage())
      const mb = (result.bytes_reclaimed / (1024 * 1024)).toFixed(1)
      onNotice?.(
        `Reclaimed ${mb} MB from ${result.files_deleted} image(s). ` +
          `Inspection records unchanged: ${result.records_after.inspections} kept.`,
      )
    } catch (err) {
      onError?.(err.message)
    } finally {
      setSaving(false)
    }
  }

  const dirty =
    thresholds && Object.keys(FIELDS).some((k) => Number(draft[k]) !== Number(thresholds[k]))

  return (
    <div className="settings">
      <section>
        <h3>Detection thresholds</h3>
        <p className="settings-note">
          Stored per board type and applied at the next inspection — no rebuild,
          no restart. Tuning values are refined against measured results, not
          standards figures.
        </p>

        {!boardTypeId && <p className="empty">Select a board type first.</p>}

        {thresholds &&
          Object.entries(FIELDS).map(([key, field]) => (
            <label key={key} className="setting-row">
              <span className="setting-label">
                {field.label}
                <span className="setting-hint">{field.hint}</span>
              </span>
              <input
                type="number"
                value={draft[key] ?? ''}
                step={field.step}
                min={field.min}
                onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                disabled={busy || saving}
              />
            </label>
          ))}

        {thresholds && (
          <button className="settings-save" onClick={save} disabled={!dirty || busy || saving}>
            {saving ? 'Saving…' : dirty ? 'Apply thresholds' : 'No changes'}
          </button>
        )}
      </section>

      <section>
        <h3>Storage</h3>
        {storage ? (
          <>
            <dl className="settings-facts">
              <div>
                <dt>Images on disk</dt>
                <dd>
                  {storage.images_present} ({storage.megabytes} MB)
                </dd>
              </div>
              <div>
                <dt>Retention window</dt>
                <dd>{storage.retention_days} days</dd>
              </div>
              <div>
                <dt>Inspection records</dt>
                <dd>{storage.records.inspections}</dd>
              </div>
            </dl>
            <p className="settings-note">
              The sweep deletes images only. Inspection records are never
              removed — they are the audit trail, and an inspection stays
              queryable long after its photograph expires.
            </p>
            <button onClick={sweep} disabled={busy || saving}>
              Run retention sweep
            </button>
          </>
        ) : (
          <p className="empty">Loading…</p>
        )}
      </section>

      <section>
        <h3>Security</h3>
        <ul className="settings-list">
          <li>
            <strong>Loopback only.</strong> The station is not reachable from
            the network. Design files are the customer's confidential IP and
            never leave this machine.
          </li>
          <li>
            <strong>No cloud services.</strong> Inspection works with every
            network interface disabled — no API call sits between placing a
            board and seeing a result.
          </li>
          <li>
            <strong>Append-only records.</strong> A correction is a new row; an
            original verdict is never edited or deleted.
          </li>
        </ul>
      </section>
    </div>
  )
}

// Kept beside the component: each hint explains what the number does in terms
// an operator can act on, not what it is called in the code.
const FIELDS = {
  diff_intensity: {
    label: 'Difference sensitivity',
    hint: 'Grey levels a pixel must change before it counts. Lower catches more, and more noise.',
    step: 1,
    min: 1,
  },
  min_region_area: {
    label: 'Minimum defect size',
    hint: 'Pixels² below which a change is treated as noise. Raise this if small specks are being flagged.',
    step: 10,
    min: 1,
  },
  blur_kernel: {
    label: 'Noise smoothing',
    hint: 'Blur applied before comparing. Higher suppresses sensor noise but blurs small parts.',
    step: 2,
    min: 1,
  },
  roi_scale: {
    label: 'Component region scale',
    hint: 'Footprint is scaled by this to form the inspected region (BR-03).',
    step: 0.05,
    min: 1,
  },
}
