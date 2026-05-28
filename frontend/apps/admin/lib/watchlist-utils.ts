type ParsedScreenParams = {
  limit?: number
  min_return_20d_pct?: number
  min_return_5d_pct?: number
  min_volume_ratio?: number
  max_return_5d_pct?: number
}

export function formatWatchlistTimestamp(value: string | null | undefined): string {
  if (!value) {
    return "-"
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(1)
}

export function parseWatchlistParams(screenParamsJson: string | null | undefined): ParsedScreenParams | null {
  if (!screenParamsJson) {
    return null
  }

  try {
    return JSON.parse(screenParamsJson) as ParsedScreenParams
  } catch {
    return null
  }
}

export function summarizeWatchlistParams(screenParamsJson: string | null | undefined): string[] {
  const parsed = parseWatchlistParams(screenParamsJson)
  if (!parsed) {
    return []
  }

  const summary: string[] = []

  if (parsed.limit != null) {
    summary.push(`数量 ${parsed.limit}`)
  }
  if (parsed.min_return_20d_pct != null) {
    summary.push(`20日最小涨幅 ${formatNumber(parsed.min_return_20d_pct)}%`)
  }
  if (parsed.min_return_5d_pct != null) {
    summary.push(`5日最小涨幅 ${formatNumber(parsed.min_return_5d_pct)}%`)
  }
  if (parsed.min_volume_ratio != null) {
    summary.push(`最小量比 ${formatNumber(parsed.min_volume_ratio)}x`)
  }
  if (parsed.max_return_5d_pct != null) {
    summary.push(`5日最大涨幅 ${formatNumber(parsed.max_return_5d_pct)}%`)
  }

  return summary
}
