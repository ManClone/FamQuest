/** Only the local server consent endpoint can resume after browser login. */
export function oauthReturnPath(search: string): string | null {
  const next = new URLSearchParams(search).get('next')
  if (!next || !next.startsWith('/authorize?') || /[\\\r\n\t]/.test(next)) return null
  const base = 'https://famquest.invalid'
  const parsed = new URL(next, base)
  return parsed.origin === base && parsed.pathname === '/authorize' ? next : null
}
