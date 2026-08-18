// Thin wrapper over the inspection API.
//
// Base URL is loopback-only by design (NFR-011). In dev the Vite server runs on
// :5173 and talks to the API on :8000; in the packaged build both are served
// from the same origin, so BASE resolves to an empty string.

const BASE = import.meta.env.DEV ? 'http://127.0.0.1:8000' : ''

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!response.ok) {
    // The API returns a specific reason in `detail` for the failures an
    // operator can actually act on (bad file, no golden reference, no camera).
    // Surfacing that verbatim beats a generic error string.
    let detail = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body.detail) detail = body.detail
    } catch {
      // Non-JSON error body; keep the status code.
    }
    throw new Error(detail)
  }
  return response.json()
}

export const streamUrl = `${BASE}/stream.mjpg`
export const exportUrl = `${BASE}/api/export.csv`

export const getHealth = () => request('/api/health')
export const listBoardTypes = () => request('/api/board-types')

export const createBoardType = (name) =>
  request('/api/board-types', { method: 'POST', body: JSON.stringify({ name }) })

export const captureGolden = (boardTypeId) =>
  request(`/api/board-types/golden?board_type_id=${boardTypeId}`, { method: 'POST' })

export const uploadPlacement = (boardTypeId, content) =>
  request('/api/board-types/placement', {
    method: 'POST',
    body: JSON.stringify({ board_type_id: boardTypeId, content }),
  })

export const uploadBom = (boardTypeId, content) =>
  request('/api/board-types/bom', {
    method: 'POST',
    body: JSON.stringify({ board_type_id: boardTypeId, content }),
  })

export const trigger = (boardTypeId) =>
  request(`/api/trigger?board_type_id=${boardTypeId}`, { method: 'POST' })

export const listInspections = (limit = 20) =>
  request(`/api/inspections?limit=${limit}`)

export const overrideRegion = (regionVerdictId) =>
  request('/api/override', {
    method: 'POST',
    body: JSON.stringify({ region_verdict_id: regionVerdictId, revised_verdict: 'false_call' }),
  })

export const regionCropUrl = (inspectionId, regionId) =>
  `${BASE}/api/inspections/${inspectionId}/regions/${regionId}.jpg`

export const selectDemoBoard = (index) =>
  request(`/api/demo/board?index=${index}`, { method: 'POST' })

export const nextDemoBoard = () => request('/api/demo/next-board', { method: 'POST' })

export const getInspection = (id) => request(`/api/inspections/${id}`)

export const checkStability = (samples = 50) =>
  request(`/api/camera/stability?samples=${samples}`)
