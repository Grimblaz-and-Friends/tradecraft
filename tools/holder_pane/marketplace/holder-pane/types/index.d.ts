// The holder pane's state contract: what its pane draws from (#888, lab-only).
export type HolderPaneFloor = { outcome: string | null; satisfied: boolean | null }
export type HolderPaneRunning = {
  stage: string
  elapsed: number
  deadline: number | null
  quiet: number
  stalled: boolean
}
export type HolderPaneView = {
  issue: number
  stage: string
  label: string
  waiting_on: string
  next_step: string
  gate: string
  floor: HolderPaneFloor
  running: HolderPaneRunning | null
  source: string | null
  read_at_local: string | null
  read_failed_local?: string
  rename_note?: string | null
  record_pending: boolean
  final: string | null
}

declare module 'claude-code' {
  interface PluginState {
    'holder-pane': { view: HolderPaneView | null }
  }
}
