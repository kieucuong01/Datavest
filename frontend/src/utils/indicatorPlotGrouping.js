export function splitIndicatorPlotsByPane (plots) {
  const source = Array.isArray(plots) ? plots : []
  return {
    overlayPlots: source.filter(plot => plot && plot.overlay !== false),
    panePlots: source.filter(plot => plot && plot.overlay === false)
  }
}
