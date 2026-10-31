/** Cryptographic 128-bit action key, also available on local HTTP displays. */
export function newRequestKey(): string {
  return Array.from(crypto.getRandomValues(new Uint8Array(16)), (byte) =>
    byte.toString(16).padStart(2, '0'),
  ).join('')
}
