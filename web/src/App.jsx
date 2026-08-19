import { useCallback, useEffect, useRef, useState } from 'react'
import Overlay from './Overlay'
import VerdictCard from './components/VerdictCard'
import DefectList from './components/DefectList'
import DemoBar from './components/DemoBar'
import History from './components/History'
import Trends from './components/Trends'
import Settings from './components/Settings'
import * as api from './api'

export default function App() {
  const [health, setHealth] = useState(null)
  const [boardTypes, setBoardTypes] = useState([])
  const [boardTypeId, setBoardTypeId] = useState(null)
  const [result, setResult] = useState(null)
  const [inspections, setInspections] = useState([])
  const [trends, setTrends] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [panel, setPanel] = useState('defects')

  const imgRef = useRef(null)
  const [naturalSize, setNaturalSize] = useState({ width: 0, height: 0 })
  const [displaySize, setDisplaySize] = useState({ width: 0, height: 0 })

  const refreshHealth = useCallback(
    () => api.getHealth().then(setHealth).catch((err) => setError(err.message)),
    [],
  )

  const refreshBoardTypes = useCallback(async () => {
    try {
      const types = await api.listBoardTypes()
      setBoardTypes(types)
      // Auto-select so a returning operator can trigger immediately rather
      // than re-picking the board they were already working on.
      setBoardTypeId((current) => current ?? types[0]?.id ?? null)
    } catch (err) {
      setError(err.message)
    }
  }, [])

  const refreshInspections = useCallback(
    () => api.listInspections(15).then(setInspections).catch(() => {}),
    [],
  )

  const refreshTrends = useCallback(() => {
    if (!boardTypeId) return
    api.getTrends(boardTypeId).then(setTrends).catch(() => {})
  }, [boardTypeId])

  useEffect(() => {
    refreshTrends()
  }, [refreshTrends])

  useEffect(() => {
    refreshHealth()
    refreshBoardTypes()
    refreshInspections()
  }, [refreshHealth, refreshBoardTypes, refreshInspections])

  // Keep the overlay canvas locked to the rendered video size. The MJPEG image
  // is responsive, so a resize would otherwise leave boxes misaligned and the
  // station would appear to blame the wrong components.
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

  const selectedBoard = boardTypes.find((b) => b.id === boardTypeId)
  const canInspect = Boolean(boardTypeId) && Boolean(selectedBoard?.golden_count)

  const handleTrigger = useCallback(
    () =>
      withBusy(async () => {
        const outcome = await api.trigger(boardTypeId)
        setResult(outcome)
        setPanel('defects')
        refreshInspections()
        refreshTrends()
        return outcome
      }),
    [boardTypeId, refreshInspections, refreshTrends],
  )

  // Space triggers, D cycles the demo board. The operator's hands are on the
  // board rather than the mouse, so the primary action needs a key.
  useEffect(() => {
    const onKey = (event) => {
      const tag = event.target?.tagName
      if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return
      if (event.code === 'Space' && canInspect && !busy) {
        event.preventDefault()
        handleTrigger()
      }
      if (event.key?.toLowerCase() === 'd' && health?.demo_mode && !busy) {
        api.nextDemoBoard().then(refreshHealth).catch(() => {})
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [canInspect, busy, handleTrigger, health?.demo_mode, refreshHealth])

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
    withBusy(async () => {
      await api.captureGolden(boardTypeId)
      await refreshBoardTypes()
      setNotice('Golden reference captured. This board is now the comparison reference.')
    })

  const readFile = (event, handler) => {
    const file = event.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => handler(String(reader.result))
    reader.readAsText(file)
    event.target.value = ''
  }

  const handleUploadPlacement = (event) =>
    readFile(event, (content) =>
      withBusy(async () => {
        const response = await api.uploadPlacement(boardTypeId, content)
        await refreshBoardTypes()
        const excluded = response.dnp_excluded
          ? ` ${response.dnp_excluded} do-not-populate designator(s) excluded.`
          : ''
        setNotice(
          `Pick-and-place loaded — ${response.component_count} components will be inspected.` +
            `${excluded} Defects will now be named by reference designator.`,
        )
      }),
    )

  // Without a BOM, a deliberately-empty designator is reported as a defect on
  // every board -- the exact false call FR-002 exists to prevent.
  const handleUploadBom = (event) =>
    readFile(event, (content) =>
      withBusy(async () => {
        const response = await api.uploadBom(boardTypeId, content)
        await refreshBoardTypes()
        setNotice(
          `BOM loaded — ${response.dnp_applied} do-not-populate designator(s) excluded. ` +
            `${response.inspectable_components} components remain inspectable.`,
        )
      }),
    )

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
      refreshInspections()
      // Overriding removes the region from the trend counts, so the panel has
      // to reflect it -- otherwise a dismissed false call keeps inflating what
      // looks like a process fault.
      refreshTrends()
    })

  const handleSelectDemoBoard = (index) =>
    withBusy(async () => {
      await api.selectDemoBoard(index)
      await refreshHealth()
      // The last result belongs to the previous board; leaving it on screen
      // would imply it describes the one now loaded.
      setResult(null)
    })

  const handleSelectBenchProfile = (name) =>
    withBusy(async () => {
      await api.selectBenchProfile(name)
      await refreshHealth()
      // Conditions changed, so the previous result no longer describes the
      // bench that produced it.
      setResult(null)
    })

  const handleStability = () =>
    withBusy(async () => {
      const stats = await api.checkStability(50)
      const deviation = stats.mean_deviation
      setNotice(
        // Saying "simulated" out loud matters: this number verifies the gate
        // works, it is not an AC-006.2 measurement of a real camera.
        `${stats.simulated ? 'Simulated frame stability' : 'Frame stability'}: ` +
          `${deviation.toFixed(2)} grey levels mean deviation — ` +
          (deviation < 2
            ? 'stable, safe to tune thresholds.'
            : 'TOO UNSTABLE — fix lighting before tuning anything.'),
      )
    })

  const handleSelectInspection = (id) =>
    withBusy(async () => {
      const record = await api.getInspection(id)
      setResult({ ...record, inspection_id: record.id })
      setPanel('defects')
    })

  const activeRegions = result?.regions?.filter((r) => !r.overridden) ?? []
  const cameraOk = health?.camera?.connected

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
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
          {selectedBoard?.dnp_count > 0 && (
            <span className="chip" title="Excluded from inspection (FR-002)">
              {selectedBoard.dnp_count} DNP excluded
            </span>
          )}
        </div>
      </header>

      <DemoBar
        demo={health?.demo}
        onSelect={handleSelectDemoBoard}
        onSelectBench={handleSelectBenchProfile}
        busy={busy}
      />

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

          <button className="trigger" onClick={handleTrigger} disabled={busy || !canInspect}>
            {busy ? 'Inspecting…' : 'Inspect board'}
            <kbd>space</kbd>
          </button>

          {selectedBoard && !selectedBoard.golden_count && (
            <p className="hint">Capture a golden reference before inspecting.</p>
          )}

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
                  {board.dnp_count ? `, ${board.dnp_count} DNP` : ''})
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
              Pick-and-place
              <input
                type="file"
                accept=".csv,.txt,.pos"
                onChange={handleUploadPlacement}
                disabled={busy || !boardTypeId}
              />
            </label>
            <label className={`file-button ${busy || !boardTypeId ? 'disabled' : ''}`}>
              BOM
              <input
                type="file"
                accept=".csv,.txt"
                onChange={handleUploadBom}
                disabled={busy || !boardTypeId}
              />
            </label>
            <button onClick={handleStability} disabled={busy}>
              Check stability
            </button>
            <a className="link-button" href={api.exportUrl}>
              Export CSV
            </a>
          </div>
        </section>

        <aside className="sidebar">
          {error && <div className="banner banner-error">{error}</div>}
          {notice && <div className="banner banner-info">{notice}</div>}

          <VerdictCard result={result} activeCount={activeRegions.length} />

          {/* A threshold warning means real defects may be going unreported.
              That is a recall risk, so it gets a warning banner rather than the
              muted hint style used for routine notes. */}
          {result?.message && (
            <div
              className={
                result.message.includes('minimum defect size')
                  ? 'banner banner-warn'
                  : 'hint'
              }
            >
              {result.message}
            </div>
          )}

          <div className="tabs">
            <button
              className={panel === 'defects' ? 'active' : ''}
              onClick={() => setPanel('defects')}
            >
              Defects{result?.regions?.length ? ` (${result.regions.length})` : ''}
            </button>
            <button
              className={panel === 'history' ? 'active' : ''}
              onClick={() => setPanel('history')}
            >
              History
            </button>
            <button
              className={panel === 'trends' ? 'active' : ''}
              onClick={() => setPanel('trends')}
            >
              Trends
            </button>
            <button
              className={panel === 'settings' ? 'active' : ''}
              onClick={() => setPanel('settings')}
            >
              Settings
            </button>
          </div>

          {panel === 'defects' && (
            <DefectList result={result} onOverride={handleOverride} busy={busy} />
          )}
          {panel === 'history' && (
            <History inspections={inspections} onSelect={handleSelectInspection} />
          )}
          {panel === 'trends' && <Trends trends={trends} />}
          {panel === 'settings' && (
            <Settings
              boardTypeId={boardTypeId}
              busy={busy}
              onNotice={setNotice}
              onError={setError}
            />
          )}
        </aside>
      </div>
    </div>
  )
}
