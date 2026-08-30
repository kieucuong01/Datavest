function readBalancedBlock (source, startIndex, openChar, closeChar) {
  let depth = 0
  let quote = ''
  let escaped = false

  for (let index = startIndex; index < source.length; index += 1) {
    const char = source[index]
    if (quote) {
      if (escaped) {
        escaped = false
      } else if (char === '\\') {
        escaped = true
      } else if (char === quote) {
        quote = ''
      }
      continue
    }
    if (char === '"' || char === "'") {
      quote = char
      continue
    }
    if (char === openChar) depth += 1
    if (char === closeChar) {
      depth -= 1
      if (depth === 0) return source.slice(startIndex, index + 1)
    }
  }
  return ''
}

function collectSignalBlocks (code) {
  const blocks = []
  const patterns = [
    /["']signals["']\s*:\s*\[/g,
    /(?:^|\n)\s*signals\s*=\s*\[/g,
    /\bsignals\s*\.\s*append\s*\(\s*\{/g
  ]

  for (const pattern of patterns) {
    let match
    while ((match = pattern.exec(code))) {
      const bracketOffset = match[0].lastIndexOf(pattern === patterns[2] ? '{' : '[')
      const startIndex = match.index + bracketOffset
      const isObject = code[startIndex] === '{'
      const block = readBalancedBlock(code, startIndex, isObject ? '{' : '[', isObject ? '}' : ']')
      if (block) blocks.push(block)
    }
  }
  return blocks
}

function decodePythonString (value) {
  return String(value || '')
    .replace(/\\([\\'"nrt])/g, (match, escaped) => {
      const replacements = { n: '\n', r: '\r', t: '\t' }
      return replacements[escaped] || escaped
    })
    .trim()
}

export function extractIndicatorSignalLabels (code) {
  const labels = []
  const seen = new Set()
  const add = (rawLabel) => {
    const label = decodePythonString(rawLabel)
    const key = label.toLocaleLowerCase()
    if (!label || seen.has(key)) return
    seen.add(key)
    labels.push(label)
  }

  for (const block of collectSignalBlocks(String(code || ''))) {
    const textPattern = /["']text["']\s*:\s*(["'])((?:\\.|(?!\1)[\s\S])*)\1/g
    let match
    while ((match = textPattern.exec(block))) add(match[2])

    const textDataPattern = /["']textData["']\s*:\s*\[/g
    while ((match = textDataPattern.exec(block))) {
      const startIndex = match.index + match[0].lastIndexOf('[')
      const listBlock = readBalancedBlock(block, startIndex, '[', ']')
      if (!listBlock) continue
      const valuePattern = /(["'])((?:\\.|(?!\1)[\s\S])*)\1/g
      let valueMatch
      while ((valueMatch = valuePattern.exec(listBlock))) add(valueMatch[2])
    }
  }

  return labels
}
