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
  wikipedia: 'Wikipedia Overview',
  price_history_annual: 'Price History (Annual)',
  price_history_weekly: 'Price History (Weekly)',
}

function titleCase(slug) {
  return slug
    .replace(/[-_]+/g, ' ')
    .split(' ')
    .filter(Boolean)
    .map((w) => (w.length <= 3 ? w.toUpperCase() : w[0].toUpperCase() + w.slice(1)))
    .join(' ')
}

export function formatDocumentLabel(filename) {
  if (!filename) return ''
  const base = filename.replace(/\.md$/i, '')
  const match = base.match(/^([a-z]+)_(\d{4}-\d{2}-\d{2})_(.+)$/i)

  if (!match) {
    // No date segment (e.g. peloton_wikipedia) — split off the company only.
    const [company, ...rest] = base.split('_')
    const companyLabel = COMPANY_LABELS[company.toLowerCase()] || titleCase(company)
    const typeSlug = rest.join('_')
    const typeLabel = TYPE_LABELS[typeSlug.toLowerCase()] || titleCase(typeSlug) || filename
    return `${companyLabel} – ${typeLabel}`
  }

  const [, company, dateStr, typeSlug] = match
  const companyLabel = COMPANY_LABELS[company.toLowerCase()] || titleCase(company)
  const typeLabel = TYPE_LABELS[typeSlug.toLowerCase()] || titleCase(typeSlug)
  return `${companyLabel} – ${typeLabel} (${formatDateShort(dateStr)})`
}
