export const CHAT_COMPOSER_STORAGE_KEY = 'marker-checker:chat-composer-draft-v2'

export const CHAT_COMPOSER_TAB = {
  MESSAGE: 'message',
  REQUEST: 'request',
} as const

export type ComposerTab = typeof CHAT_COMPOSER_TAB[keyof typeof CHAT_COMPOSER_TAB]

export type SlashCommandCategory = 'General' | 'Requests' | 'Approvals'

export type SlashCommand = {
  cmd: string
  args?: string
  desc: string
  category: SlashCommandCategory
}

export const SLASH_COMMANDS: SlashCommand[] = [
  { cmd: '/help', desc: 'Show all available commands', category: 'General' },
  { cmd: '/mypending', desc: 'List your active requests', category: 'Requests' },
  { cmd: '/status', args: 'REQ-XXXX', desc: 'View request status & details', category: 'Requests' },
  { cmd: '/history', args: 'REQ-XXXX', desc: 'Full event timeline of a request', category: 'Requests' },
  { cmd: '/search', args: '<query>', desc: 'Search requests by target name', category: 'Requests' },
  { cmd: '/confirm', desc: 'Submit your pending draft', category: 'Requests' },
  { cmd: '/discard', desc: 'Cancel your pending draft', category: 'Requests' },
  { cmd: '/resubmit', args: 'REQ-XXXX <message>', desc: 'Revise & resubmit after need-info', category: 'Requests' },
  { cmd: '/myapprovals', desc: 'List requests waiting for your approval', category: 'Approvals' },
  { cmd: '/approve', args: 'REQ-XXXX [note]', desc: 'Approve a request', category: 'Approvals' },
  { cmd: '/reject', args: 'REQ-XXXX [reason]', desc: 'Reject a request', category: 'Approvals' },
  { cmd: '/needinfo', args: 'REQ-XXXX [question]', desc: 'Ask requester for more information', category: 'Approvals' },
  { cmd: '/cancel', args: 'REQ-XXXX [note]', desc: 'Cancel a request', category: 'Approvals' },
]

export const SLASH_COMMAND_CATEGORY_ORDER: SlashCommandCategory[] = [
  'General',
  'Requests',
  'Approvals',
]

export const EDITOR_LANGUAGE = {
  YAML: 'yaml',
  JSON: 'json',
  JAVASCRIPT: 'javascript',
  TYPESCRIPT: 'typescript',
  PYTHON: 'python',
  BASH: 'bash',
  GO: 'go',
  SQL: 'sql',
  RUST: 'rust',
  HTML: 'html',
  CSS: 'css',
  TOML: 'toml',
  TEXT: 'text',
} as const

export type EditorLanguage = typeof EDITOR_LANGUAGE[keyof typeof EDITOR_LANGUAGE]

export const LANGUAGE_GROUPS: {
  label: string
  langs: { value: EditorLanguage; label: string }[]
}[] = [
  {
    label: 'Data / Config',
    langs: [
      { value: EDITOR_LANGUAGE.YAML, label: 'YAML' },
      { value: EDITOR_LANGUAGE.JSON, label: 'JSON' },
      { value: EDITOR_LANGUAGE.TOML, label: 'TOML' },
    ],
  },
  {
    label: 'Code',
    langs: [
      { value: EDITOR_LANGUAGE.JAVASCRIPT, label: 'JavaScript' },
      { value: EDITOR_LANGUAGE.TYPESCRIPT, label: 'TypeScript' },
      { value: EDITOR_LANGUAGE.PYTHON, label: 'Python' },
      { value: EDITOR_LANGUAGE.BASH, label: 'Bash' },
      { value: EDITOR_LANGUAGE.GO, label: 'Go' },
      { value: EDITOR_LANGUAGE.RUST, label: 'Rust' },
      { value: EDITOR_LANGUAGE.SQL, label: 'SQL' },
    ],
  },
  {
    label: 'Web',
    langs: [
      { value: EDITOR_LANGUAGE.HTML, label: 'HTML' },
      { value: EDITOR_LANGUAGE.CSS, label: 'CSS' },
    ],
  },
  {
    label: 'Other',
    langs: [
      { value: EDITOR_LANGUAGE.TEXT, label: 'Plain text' },
    ],
  },
]

export const COMPOSER_SHORTCUT_HINTS = [
  ['↑↓', 'navigate'],
  ['↵', 'select'],
  ['Esc', 'close'],
] as const
