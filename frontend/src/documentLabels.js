// Turns a raw source filename like "peloton_2020-12-21_8k.md" into a
// human-readable label like "Peloton – Form 8-K (Dec 21)", for display
// anywhere a document is referenced in the UI (dropdowns, viewer titles,
// etc). The date suffix matters because a single event can cite two
// documents of the same type filed on different days (e.g. two 8-Ks a few
// days apart), which would otherwise be indistinguishable in a list.

const COMPANY_LABELS = {
  peloton: 'Peloton',
}

const MONTH_ABBR = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function formatDateShort(dateStr) {
  // dateStr: "2022-02-05" — parsed manually (not via Date) to avoid any
  // timezone-shift surprises with date-only ISO strings.
  const [year, month, day] = dateStr.split('-').map(Number)
  return `${MONTH_ABBR[month - 1]} ${day}, ${year}`
}

const TYPE_LABELS = {
  '8k': 'Form 8-K',
  '10k': 'Form 10-K',
  '10q': 'Form 10-Q',
  pr: 'Press Release',
  'board-pr': 'Board Press Release',
  'restructuring-pr': 'Restructuring Press Release',
  'shareholder-letter': 'Shareholder Letter',
  'shareholder-letter_v2': 'Shareholder Letter (Amended)',
}

// Short badge form of TYPE_LABELS for dense UI (terminal source tabs) where
// the full "Form 8-K" label doesn't fit — same keys, compact values.
const KIND_LABELS = {
  '8k': '8-K',
  '10k': '10-K',
  '10q': '10-Q',
  pr: 'PR',
  'board-pr': 'BOARD PR',
  'restructuring-pr': 'RESTRUCT PR',
  'shareholder-letter': 'LETTER',
  'shareholder-letter_v2': 'LETTER v2',
}

function titleCase(slug) {
  return slug
    .replace(/[-_]+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1)))
    .join(' ')
}

function parseFilename(filename) {
  const base = (filename || '').replace(/\.md$/i, '')
  const match = base.match(/^([a-z]+)_(\d{4}-\d{2}-\d{2})_(.+)$/i)
  if (!match) {
    const [company, ...rest] = base.split('_')
    return { company, dateStr: null, typeSlug: rest.join('_') }
  }
  const [, company, dateStr, typeSlug] = match
  return { company, dateStr, typeSlug }
}

export function formatDocumentLabel(filename) {
  if (!filename) return ''
  const { company, dateStr, typeSlug } = parseFilename(filename)
  const companyLabel = COMPANY_LABELS[company.toLowerCase()] || titleCase(company)
  const typeLabel = TYPE_LABELS[typeSlug.toLowerCase()] || titleCase(typeSlug) || filename
  if (!dateStr) return `${companyLabel} – ${typeLabel}`
  return `${companyLabel} – ${typeLabel} (${formatDateShort(dateStr)})`
}

// Compact "kind" badge, e.g. "8-K" — used by the terminal source tabs
// instead of the full formatDocumentLabel string.
export function formatDocumentKind(filename) {
  if (!filename) return ''
  const { typeSlug } = parseFilename(filename)
  return KIND_LABELS[typeSlug.toLowerCase()] || titleCase(typeSlug).toUpperCase()
}
