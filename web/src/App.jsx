import { useCallback, useEffect, useRef, useState } from 'react'
import Overlay from './Overlay'
import * as api from './api'

export default function App() {
  const [health, setHealth] = useState(null)
  const [boardTypes, setBoardTypes] = useState([])
  const [boardTypeId, setBoardTypeId] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const imgRef = useRef(null)
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 })
  const [displaySize, setDisplaySize] = useState({ width: 0, height: 0 })

  const refreshBoardTypes = useCallback(async () => {
    try {
      const types = await api.listBoardTypes()
      setBoardTypes(types)
      // Auto-select so a returning operator can trigger immediately without
      // re-picking the board they were already working on.
      setBoardTypeId((current) => current ?? types[0]?.id ?? null)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  useEffect(() => {
    api.getHealth().then(setHealth).catch((err) => setError(err.message))
    refreshBoardTypes()
  }, [refreshBoardTypes])

  // Keep the overlay canvas locked to the rendered video size. The MJPEG image
  // is responsive, so a window resize would otherwise leave boxes misaligned.
  useEffect(() => {
    const element = imgRef.current
    if (!element) return

    const sync = () => {
      setDisplaySize({ width: element.clientWidth, height: element.clientHeight })
      if (element.naturalWidth) {
        setNaturalSize({ width: element.naturalWidth, height: element.naturalHeight })
      }
    }
    sync()
    const observer = new ResizeObserver(sync)
    observer.observe(element)
    element.addEventListener('load', sync)
    return () => {
      observer.disconnect()
      element.removeEventListener('load', sync)
    }
  }, [])

  const withBusy = async (fn, successMessage) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const value = await fn()
      if (successMessage) setNotice(successMessage)
      return value
    } catch (err) {
      setError(err.message)
      return null
    } finally {
      setBusy(false)
    }
  }

  const handleCreateBoardType = () =>
    withBusy(async () => {
      const name = window.prompt('Board type name')
      if (!name) return null
      const created = await api.createBoardType(name)
      await refreshBoardTypes()
      setBoardTypeId(created.board_type_id)
      return created
    })

  const handleCaptureGolden = () =>
    withBusy(
      () => api.captureGolden(boardTypeId),
      'Golden reference captured. This board is now the reference for comparison.',
    )

  const handleTrigger = () =>
    withBusy(async () => {
      const outcome = await api.trigger(boardTypeId)
      setResult(outcome)
      return outcome
    })

  const handleUploadPlacement = (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () =>
      withBusy(async () => {
        const response = await api.uploadPlacement(boardTypeId, String(reader.result))
        await refreshBoardTypes()
        // Surface the exclusion count rather than only the loaded count: a
        // technician needs to notice if the file knocks out part of the board.
        const excluded = response.dnp_excluded
          ? ` ${response.dnp_excluded} do-not-populate designator(s) excluded.`
          : ''
        setNotice(
          `Pick-and-place loaded — ${response.component_count} components will be ` +
            `inspected.${excluded} Defects will now be named by reference designator.`,
        )
        return response
      })
    reader.readAsText(file)
  }

  // The BOM is authoritative for do-not-populate state. Without it, a
  // deliberately-empty designator is reported as a defect on every board.
  const handleUploadBom = (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () =>
      withBusy(async () => {
        const response = await api.uploadBom(boardTypeId, String(reader.result))
        await refreshBoardTypes()
        setNotice(
          `BOM loaded — ${response.dnp_applied} do-not-populate designator(s) ` +
            `excluded from inspection. ${response.inspectable_components} components remain.`,
        )
        return response
      })
    reader.readAsText(file)
  }

  // Overriding is one click by design. An operator who has to fill in a form to
  // dismiss a false call stops dismissing them and starts ignoring the station.
  const handleOverride = (regionId) =>
    withBusy(async () => {
      await api.overrideRegion(regionId)
      setResult((current) =>
        current && {
          ...current,
          regions: current.regions.map((region) =>
            region.id === regionId
              ? { ...region, overridden: true, verdict: 'false_call' }
              : region,
          ),
        },
      )
    })

  const handleStability = () =>
    withBusy(async () => {
      const stats = await api.checkStability(50)
      const deviation = stats.mean_deviation
      // Below 2 grey levels is the gate from AC-006.2. Above it, any threshold
      // tuned downstream stops being true the moment the light shifts.
      setNotice(
        `Frame stability: ${deviation.toFixed(2)} grey levels mean deviation — ` +
          (deviation < 2 ? 'stable, safe to tune thresholds.' : 'TOO UNSTABLE, fix lighting first.'),
      )
      return stats
    })

  const selectedBoard = boardTypes.find((b) => b.id === boardTypeId)
  const activeRegions = result?.regions?.filter((r) => !r.overridden) ?? []
  const cameraOk = health?.camera?.connected

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>GerberEye</h1>
          <p className="subtitle">CAD-referenced optical inspection</p>
        </div>
        <div className="status-cluster">
          <span className={`chip ${cameraOk ? 'chip-ok' : 'chip-bad'}`}>
            {cameraOk ? 'Camera connected' : 'No camera'}
          </span>
          {health?.camera?.settings_locked === false && (
            <span className="chip chip-warn" title={health.camera.degraded_reason ?? ''}>
              Settings unlocked
            </span>
          )}
        </div>
      </header>

      <div className="layout">
        <section className="video-panel">
          <div className="video-wrap">
            <img ref={imgRef} src={api.streamUrl} alt="Live board view" className="video" />
            <Overlay
              regions={result?.regions ?? []}
              naturalSize={naturalSize}
              displaySize={displaySize}
            />
          </div>

          <div className="controls">
            <select
              value={boardTypeId ?? ''}
              onChange={(e) => setBoardTypeId(Number(e.target.value))}
              disabled={busy}
            >
              <option value="" disabled>
                Select board type
              </option>
              {boardTypes.map((board) => (
                <option key={board.id} value={board.id}>
                  {board.name} ({board.component_count} components
                  {board.dnp_count ? `, ${board.dnp_count} DNP excluded` : ''})
                </option>
              ))}
            </select>

            <button onClick={handleCreateBoardType} disabled={busy}>
              New board type
            </button>
            <button onClick={handleCaptureGolden} disabled={busy || !boardTypeId}>
              Capture golden
            </button>
            <label className={`file-button ${busy || !boardTypeId ? 'disabled' : ''}`}>
              Load pick-and-place
              <input type="file" accept=".csv,.txt,.pos" onChange={handleUploadPlacement} disabled={busy || !boardTypeId} />
            </label>
            <label className={`file-button ${busy || !boardTypeId ? 'disabled' : ''}`}>
              Load BOM
              <input type="file" accept=".csv,.txt" onChange={handleUploadBom} disabled={busy || !boardTypeId} />
            </label>
            <button onClick={handleStability} disabled={busy}>
              Check stability
            </button>
            <a className="link-button" href={api.exportUrl}>
              Export CSV
            </a>
          </div>

          <button
            className="trigger"
            onClick={handleTrigger}
            disabled={busy || !boardTypeId || !selectedBoard?.golden_count}
          >
            {busy ? 'Inspecting…' : 'Inspect board'}
          </button>
          {selectedBoard && !selectedBoard.golden_count && (
            <p className="hint">Capture a golden reference before inspecting.</p>
          )}
        </section>

        <aside className="sidebar">
          {error && <div className="banner banner-error">{error}</div>}
          {notice && <div className="banner banner-info">{notice}</div>}

          {result && (
            <div className={`verdict verdict-${result.verdict}`}>
              <span className="verdict-word">{result.verdict.toUpperCase()}</span>
              <span className="verdict-meta">
                {activeRegions.length} active {activeRegions.length === 1 ? 'defect' : 'defects'}
                {' · '}
                {result.path_used === 'cad' ? 'CAD-referenced' : 'golden differencing'}
              </span>
            </div>
          )}

          {result?.message && <p className="hint">{result.message}</p>}

          <h2>Defects</h2>
          {!result && <p className="empty">Run an inspection to see results.</p>}
          {result && result.regions.length === 0 && (
            <p className="empty">No deviations from the reference.</p>
          )}

          <ul className="defect-list">
            {result?.regions.map((region, index) => (
              <li key={region.id ?? index} className={region.overridden ? 'dismissed' : ''}>
                <div className="defect-main">
                  <span className="defect-name">{region.ref_des ?? `Region ${index + 1}`}</span>
                  <span className="defect-meta">{region.area_px} px²</span>
                </div>
                {region.overridden ? (
                  <span className="dismissed-tag">dismissed</span>
                ) : (
                  <button className="override" onClick={() => handleOverride(region.id)} disabled={busy}>
                    False call
                  </button>
                )}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  )
}
