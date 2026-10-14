import { type FormEvent, useState } from 'react'

import { useCreditWeeklyAllowance, useMoneyOverview, useWeeklyAllowanceStatus, useWeeklyAllowanceSettings, useSaveWeeklyAllowanceSettings } from '../../api/money'
import type { Member } from '../../api/members'
import { Alert, Button, Section } from '../../components/ui'

const euros = (cents: number) =>
  new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(cents / 100)

/** A deliberate manual parent action. No automatic schedule or bank payout. */
export function PocketMoneySection({ children }: { children: Member[] }) {
  const [memberId, setMemberId] = useState<number | null>(null)
  const selected = children.find((child) => child.id === memberId) ?? children[0]
  const overview = useMoneyOverview(selected?.id ?? 0)
  const credit = useCreditWeeklyAllowance(selected?.id ?? 0)
  const [amount, setAmount] = useState('')
  const [monday, setMonday] = useState('')
  const [message, setMessage] = useState('')
  const [weeklyAmount, setWeeklyAmount] = useState('')
  const settings = useWeeklyAllowanceSettings(selected?.id ?? 0)
  const saveSettings = useSaveWeeklyAllowanceSettings(selected?.id ?? 0)
  const parseCents = (value: string) => {
    const normalized = value.trim().replace(',', '.')
    if (!/^(?:\d{1,4})(?:\.\d{1,2})?$/.test(normalized)) return null
    const cents = Math.round(Number(normalized) * 100)
    return cents >= 1 && cents <= 100000 ? cents : null
  }
  const weeklyStatus = useWeeklyAllowanceStatus(selected?.id ?? 0, monday)

  const submit = (event: FormEvent) => {
    event.preventDefault()
    setMessage('')
    const normalized = amount.trim().replace(',', '.')
    if (!/^(?:\d{1,4})(?:\.\d{1,2})?$/.test(normalized)) {
      setMessage('Bitte einen gültigen Eurobetrag mit höchstens zwei Nachkommastellen eingeben.')
      return
    }
    const cents = Math.round(Number(normalized) * 100)
    if (!Number.isSafeInteger(cents) || cents < 1 || cents > 100000) {
      setMessage('Bitte einen Betrag zwischen 0,01 € und 1.000 € eingeben.')
      return
    }
    const date = new Date(`${monday}T12:00:00Z`)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(monday) || Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== monday || date.getUTCDay() !== 1) {
      setMessage('Bitte einen Montag auswählen.')
      return
    }
    credit.mutate(
      { amount_cents: cents, week_start: monday },
      {
        onSuccess: (result) =>
          setMessage(
            result.booked
              ? 'Grundtaschengeld wurde gutgeschrieben.'
              : 'Für diese Woche wurde bereits Grundtaschengeld gutgeschrieben.',
          ),
      },
    )
  }

  return (
    <Section title="Taschengeld">
      {children.length === 0 ? (
        <p>Lege zuerst ein Kind in der Familienverwaltung an.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 font-bold">
            Kind
            <select
              value={selected.id}
              onChange={(event) => {
                setMemberId(Number(event.target.value))
                setMessage('')
              }}
              className="min-h-12 rounded-xl border-2 border-slate-200 bg-white p-2"
            >
              {children.map((child) => (
                <option key={child.id} value={child.id}>{child.name}</option>
              ))}
            </select>
          </label>
          {overview.isPending && <p>Geldstände werden geladen …</p>}
          {overview.isError && <Alert>Geldstände konnten nicht geladen werden.</Alert>}
          {overview.data && (
            <dl className="grid grid-cols-2 gap-3">
              <div><dt>Grundtaschengeld</dt><dd className="font-bold">{euros(overview.data.allowance_cents)}</dd></div>
              <div><dt>Quest-Boni</dt><dd className="font-bold">{euros(overview.data.bonus_cents)}</dd></div>
              <div><dt>Gesamt</dt><dd className="font-bold">{euros(overview.data.total_cents)}</dd></div>
            </dl>
          )}
          <form
            onSubmit={(event) => {
              event.preventDefault()
              const cents = parseCents(weeklyAmount)
              if (cents === null) {
                setMessage('Bitte einen gültigen Wochenbetrag eingeben.')
                return
              }
              saveSettings.mutate(cents, { onSuccess: () => setMessage('Wochenbetrag gespeichert. Die Buchung erfolgt automatisch.') })
            }}
            className="flex flex-col gap-3"
          >
            <p className="font-bold">Automatisches wöchentliches Grundtaschengeld</p>
            <p>Aktuell: {settings.data?.weekly_amount_cents == null ? 'Nicht eingerichtet' : euros(settings.data.weekly_amount_cents)}</p>
            <label className="flex flex-col gap-1">
              Wochenbetrag in Euro
              <input inputMode="decimal" value={weeklyAmount} onChange={(event) => setWeeklyAmount(event.target.value)}
                placeholder="Betrag selbst festlegen" className="min-h-12 rounded-xl border-2 border-slate-200 p-2" />
            </label>
            {saveSettings.isError && <Alert>Wochenbetrag konnte nicht gespeichert werden.</Alert>}
            <Button type="submit" disabled={saveSettings.isPending}>Wochenbetrag speichern</Button>
            {settings.data?.weekly_amount_cents != null && (
              <Button type="button" disabled={saveSettings.isPending}
                onClick={() => saveSettings.mutate(null, { onSuccess: () => setMessage('Automatische Gutschrift deaktiviert.') })}>
                Automatik deaktivieren
              </Button>
            )}
          </form>
          <form onSubmit={submit} className="flex flex-col gap-3">
            <p className="font-bold">Wöchentliches Grundtaschengeld manuell gutschreiben</p>
            <label className="flex flex-col gap-1">
              Betrag in Euro
              <input
                required inputMode="decimal" placeholder="z. B. 5,00" value={amount}
                onChange={(event) => setAmount(event.target.value)}
                className="min-h-12 rounded-xl border-2 border-slate-200 p-2"
              />
            </label>
            <label className="flex flex-col gap-1">
              Wochenbeginn (Montag)
              <input
                required type="date" value={monday}
                onChange={(event) => setMonday(event.target.value)}
                className="min-h-12 rounded-xl border-2 border-slate-200 p-2"
              />
            </label>
            {weeklyStatus.data?.booked && <p role="status">Für diese Woche wurde bereits Grundtaschengeld gebucht.</p>}
            {message && <p role="status">{message}</p>}
            {credit.isError && <Alert>Gutschrift fehlgeschlagen. Bitte Angaben prüfen.</Alert>}
            <Button type="submit" disabled={credit.isPending || weeklyStatus.data?.booked === true}>
              {credit.isPending ? 'Buche …' : 'Grundtaschengeld gutschreiben'}
            </Button>
          </form>
          <p className="text-sm text-slate-500">Automatische Buchung nur bei konfiguriertem Wochenbetrag. Keine Banküberweisung. Quest-Boni bleiben getrennt.</p>
        </div>
      )}
    </Section>
  )
}
