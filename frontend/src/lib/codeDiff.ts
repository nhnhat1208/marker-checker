export type DiffEntry = {
  type: 'unchanged' | 'added' | 'removed'
  line: string
}

export function computeLineDiff(beforeText: string, afterText: string): DiffEntry[] {
  const beforeLines = beforeText.replace(/\r\n/g, '\n').split('\n')
  const afterLines = afterText.replace(/\r\n/g, '\n').split('\n')
  const rows = beforeLines.length
  const cols = afterLines.length

  const lcs = Array.from({ length: rows + 1 }, () => Array<number>(cols + 1).fill(0))

  for (let row = rows - 1; row >= 0; row -= 1) {
    for (let col = cols - 1; col >= 0; col -= 1) {
      if (beforeLines[row] === afterLines[col]) {
        lcs[row][col] = lcs[row + 1][col + 1] + 1
      } else {
        lcs[row][col] = Math.max(lcs[row + 1][col], lcs[row][col + 1])
      }
    }
  }

  const entries: DiffEntry[] = []
  let row = 0
  let col = 0

  while (row < rows && col < cols) {
    if (beforeLines[row] === afterLines[col]) {
      entries.push({ type: 'unchanged', line: beforeLines[row] })
      row += 1
      col += 1
      continue
    }

    if (lcs[row + 1][col] >= lcs[row][col + 1]) {
      entries.push({ type: 'removed', line: beforeLines[row] })
      row += 1
    } else {
      entries.push({ type: 'added', line: afterLines[col] })
      col += 1
    }
  }

  while (row < rows) {
    entries.push({ type: 'removed', line: beforeLines[row] })
    row += 1
  }

  while (col < cols) {
    entries.push({ type: 'added', line: afterLines[col] })
    col += 1
  }

  return entries
}

export function summarizeDiff(entries: DiffEntry[]) {
  return entries.reduce(
    (acc, entry) => {
      acc[entry.type] += 1
      return acc
    },
    { added: 0, removed: 0, unchanged: 0 },
  )
}

export function getChangedEntries(entries: DiffEntry[], limit = 10) {
  const changed = entries.filter(entry => entry.type !== 'unchanged')

  return {
    entries: changed.slice(0, limit),
    hiddenCount: Math.max(0, changed.length - limit),
    totalChanged: changed.length,
  }
}
