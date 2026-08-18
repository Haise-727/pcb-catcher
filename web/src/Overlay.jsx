import { useEffect, useRef } from 'react'

// Defect boxes are drawn on a canvas layered over the MJPEG <img> rather than
// composited server-side. Keeping the overlay client-side means the video
// stream stays a plain image the browser decodes natively, and re-rendering
// after an override costs nothing.
//
// Colour alone never carries the verdict: every box also gets a text label and
// overridden boxes switch to a dashed stroke, so the display stays readable
// for a colour-blind operator (NFR-008).
export default function Overlay({ regions, naturalSize, displaySize }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || !displaySize.width || !displaySize.height) return

    canvas.width = displaySize.width
    canvas.height = displaySize.height
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (!regions?.length || !naturalSize.width || !naturalSize.height) return

    // The inspection ran on a full-resolution frame; the <img> is scaled to fit
    // the panel. Boxes must be scaled by the same factor or they land in the
    // wrong place, which would blame the wrong component.
    const scaleX = displaySize.width / naturalSize.width
    const scaleY = displaySize.height / naturalSize.height

    regions.forEach((region, index) => {
      const [x, y, w, h] = region.bbox
      const isOverridden = region.overridden
      const left = x * scaleX
      const top = y * scaleY
      const width = w * scaleX
      const height = h * scaleY

      ctx.lineWidth = 2
      ctx.strokeStyle = isOverridden ? '#8a8f98' : '#e5484d'
      ctx.setLineDash(isOverridden ? [6, 4] : [])
      ctx.strokeRect(left, top, width, height)

      const label = region.ref_des ?? `R${index + 1}`
      const text = isOverridden ? `${label} (dismissed)` : label

      ctx.setLineDash([])
      ctx.font = '600 13px ui-monospace, SFMono-Regular, Menlo, monospace'
      const metrics = ctx.measureText(text)
      const padding = 4
      const labelHeight = 18
      // Nudge the label inside the frame when the box sits at the very top,
      // otherwise it renders off-screen and the operator cannot read it.
      const labelTop = top - labelHeight < 0 ? top + height : top - labelHeight

      ctx.fillStyle = isOverridden ? '#8a8f98' : '#e5484d'
      ctx.fillRect(left, labelTop, metrics.width + padding * 2, labelHeight)
      ctx.fillStyle = '#ffffff'
      ctx.fillText(text, left + padding, labelTop + 13)
    })
  }, [regions, naturalSize, displaySize])

  return <canvas ref={canvasRef} className="overlay-canvas" />
}
