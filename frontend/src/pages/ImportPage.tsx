import { useRef, useState, type DragEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, Database, Download, FileSpreadsheet, Play, Upload } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { PageHeader } from '@/components/ui/PageHeader'
import { Card, CardBody, CardHeader } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState, ErrorNotice, Spinner } from '@/components/ui/Feedback'
import { cn, formatDateTime, formatNumber } from '@/lib/utils'
import type { ImportRecord, ImportResult } from '@/lib/types'

const ACCEPT = '.xlsx,.csv'
const MAX_MB = 10

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback
}

function SheetCounts({ result }: { result: ImportResult }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
            <th className="px-5 py-2.5 font-medium">Sheet</th>
            <th className="px-5 py-2.5 text-right font-medium">Rows</th>
            <th className="px-5 py-2.5 text-right font-medium">New</th>
            <th className="px-5 py-2.5 text-right font-medium">Updated</th>
          </tr>
        </thead>
        <tbody>
          {result.sheets.map((s) => (
            <tr key={s.sheet} className="border-b border-border last:border-0">
              <td className="px-5 py-2.5 font-medium text-slate-900">{s.sheet}</td>
              <td className="px-5 py-2.5 text-right tabular-nums">{formatNumber(s.rows)}</td>
              <td className="px-5 py-2.5 text-right tabular-nums text-ok-700">{formatNumber(s.created)}</td>
              <td className="px-5 py-2.5 text-right tabular-nums text-slate-600">{formatNumber(s.updated)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function IssuesTable({ result }: { result: ImportResult }) {
  return (
    <div className="flex flex-col gap-3">
      <ErrorNotice
        title={`${formatNumber(result.error_count)} problem${result.error_count === 1 ? '' : 's'} found — nothing was saved`}
        message="Fix these rows in your file and upload it again."
      />
      <div className="max-h-96 overflow-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-white">
            <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
              <th className="px-4 py-2 font-medium">Sheet</th>
              <th className="px-4 py-2 font-medium">Row</th>
              <th className="px-4 py-2 font-medium">Column</th>
              <th className="px-4 py-2 font-medium">Problem</th>
            </tr>
          </thead>
          <tbody>
            {result.errors.map((e, i) => (
              <tr key={i} className="border-b border-border last:border-0">
                <td className="whitespace-nowrap px-4 py-2 font-medium text-slate-900">{e.sheet}</td>
                <td className="px-4 py-2 tabular-nums text-muted">{e.row ?? '—'}</td>
                <td className="whitespace-nowrap px-4 py-2 font-mono text-xs text-muted">{e.column ?? '—'}</td>
                <td className="px-4 py-2 text-slate-900">{e.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.error_count > result.errors.length && (
        <p className="text-xs text-muted">
          Showing the first {result.errors.length} of {formatNumber(result.error_count)} problems.
        </p>
      )}
    </div>
  )
}

function DemoDataCard() {
  const queryClient = useQueryClient()
  const [confirming, setConfirming] = useState(false)
  const reload = useMutation({
    mutationFn: async () => {
      await api.loadDemoData(true)
      return api.runNetwork({})
    },
    onSuccess: () => {
      setConfirming(false)
      queryClient.invalidateQueries()
    },
  })

  return (
    <Card>
      <CardHeader
        title="Demo data"
        description="Admins only. Replaces all planning data and run history with the demo network, with sales history ending yesterday, then runs the pipeline. Users and the activity log are kept."
      />
      <CardBody className="flex flex-col gap-3">
        {reload.isError && <ErrorNotice message={errorMessage(reload.error, 'Reloading demo data failed')} />}
        {reload.isSuccess && (
          <p className="flex flex-wrap items-center gap-2 text-sm text-ok-700">
            <CheckCircle2 className="h-4 w-4" /> Demo data reloaded.
            <Link to={`/runs/${reload.data.pipeline_run_id}`} className="font-medium text-brand-600 hover:text-brand-700">
              View the pipeline run →
            </Link>
          </p>
        )}
        {!confirming ? (
          <div>
            <Button variant="secondary" onClick={() => { reload.reset(); setConfirming(true) }}>
              <Database className="h-4 w-4" /> Reset to fresh demo data
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3 rounded-lg border border-danger-600/20 bg-danger-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-danger-700">
              This deletes every location, SKU, policy, stock and sales row, all runs and alerts. It can’t be undone.
            </p>
            <div className="flex shrink-0 gap-2">
              <Button variant="danger" size="sm" onClick={() => reload.mutate()} loading={reload.isPending}>
                {reload.isPending ? 'Reloading…' : 'Yes, replace everything'}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setConfirming(false)} disabled={reload.isPending}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  )
}

function summarize(record: ImportRecord): string {
  if (!record.summary) return '—'
  return Object.entries(record.summary)
    .map(([sheet, c]) => `${sheet}: ${formatNumber(c.created)} new, ${formatNumber(c.updated)} updated`)
    .join(' · ')
}

export function ImportPage() {
  const { can } = useAuth()
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const history = useQuery({ queryKey: ['imports'], queryFn: () => api.listImports(20) })

  const preview = useMutation({ mutationFn: (f: File) => api.uploadImport(f, true) })
  const commit = useMutation({
    mutationFn: (f: File) => api.uploadImport(f, false),
    onSuccess: () => queryClient.invalidateQueries(),
  })
  const runPipeline = useMutation({ mutationFn: () => api.runNetwork({}) })
  const template = useMutation({ mutationFn: (includeData: boolean) => api.downloadTemplate(includeData) })

  function choose(f: File | null | undefined) {
    setLocalError(null)
    preview.reset()
    commit.reset()
    runPipeline.reset()
    if (!f) return setFile(null)
    if (!/\.(xlsx|csv)$/i.test(f.name)) {
      setFile(null)
      return setLocalError('Choose an .xlsx workbook (or a .csv for a single sheet).')
    }
    if (f.size > MAX_MB * 1024 * 1024) {
      setFile(null)
      return setLocalError(`The file is larger than ${MAX_MB} MB. Split it into smaller files.`)
    }
    setFile(f)
    preview.mutate(f)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    choose(e.dataTransfer.files?.[0])
  }

  function startOver() {
    choose(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const result = commit.data ?? preview.data
  const totalRows = result?.sheets.reduce((n, s) => n + s.rows, 0) ?? 0

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Data"
        title="Data import"
        description="Bring your own locations, SKUs, lanes, policies, stock and sales history from Excel. Every row is checked before anything is saved, and a file is saved completely or not at all."
      />

      <Card>
        <CardHeader title="1. Get the template" description="Six sheets: Locations, Products, Lanes, Policies, Inventory and Demand. Fill in only the ones you need." />
        <CardBody className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
          <Button variant="secondary" onClick={() => template.mutate(false)} loading={template.isPending && template.variables === false}>
            <Download className="h-4 w-4" /> Blank template
          </Button>
          <Button variant="secondary" onClick={() => template.mutate(true)} loading={template.isPending && template.variables === true}>
            <Download className="h-4 w-4" /> Current data (to edit and re-upload)
          </Button>
          {template.isError && <ErrorNotice message={errorMessage(template.error, 'Download failed')} />}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="2. Upload and check" description={`.xlsx (any of the six sheets) or .csv (one sheet), up to ${MAX_MB} MB.`} />
        <CardBody className="flex flex-col gap-4">
          {!file && (
            <label
              onDragOver={(e) => {
                e.preventDefault()
                setDragging(true)
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
                dragging ? 'border-brand-500 bg-brand-50' : 'border-border hover:border-brand-500 hover:bg-slate-50',
              )}
            >
              <Upload className="h-8 w-8 text-slate-400" />
              <span className="text-sm font-medium text-slate-900">Drop your file here, or click to choose</span>
              <span className="text-xs text-muted">Nothing is saved until you confirm</span>
              <input
                ref={inputRef}
                type="file"
                accept={ACCEPT}
                className="sr-only"
                onChange={(e) => choose(e.target.files?.[0])}
              />
            </label>
          )}

          {localError && <ErrorNotice title="Can’t use this file" message={localError} />}

          {file && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border px-4 py-3">
              <div className="flex min-w-0 items-center gap-3">
                <FileSpreadsheet className="h-5 w-5 shrink-0 text-ok-600" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
                  <p className="text-xs text-muted">{formatNumber(file.size / 1024, 0)} KB</p>
                </div>
              </div>
              <Button variant="ghost" size="sm" onClick={startOver} disabled={commit.isPending}>
                Choose another file
              </Button>
            </div>
          )}

          {preview.isPending && <Spinner label="Checking every row…" />}
          {preview.isError && <ErrorNotice title="Couldn’t read the file" message={errorMessage(preview.error, 'Upload failed')} />}

          {result && result.warnings.length > 0 && (
            <div className="flex items-start gap-2 rounded-lg bg-warn-50 px-4 py-3 text-sm text-warn-700">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <ul className="list-inside">
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          {result && result.error_count > 0 && <IssuesTable result={result} />}

          {result && result.error_count === 0 && !result.committed && (
            <div className="flex flex-col gap-4">
              <p className="flex items-center gap-2 text-sm text-ok-700">
                <CheckCircle2 className="h-4 w-4" /> All {formatNumber(totalRows)} rows are valid. Here’s what will change:
              </p>
              <div className="rounded-lg border border-border">
                <SheetCounts result={result} />
              </div>
              {commit.isError && <ErrorNotice title="Import failed — nothing was saved" message={errorMessage(commit.error, 'Please try again.')} />}
              <div className="flex flex-wrap gap-2">
                <Button onClick={() => file && commit.mutate(file)} loading={commit.isPending}>
                  Import {formatNumber(totalRows)} rows
                </Button>
                <Button variant="secondary" onClick={startOver} disabled={commit.isPending}>
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {result?.committed && (
            <div className="flex flex-col gap-4">
              <p className="flex items-center gap-2 rounded-lg bg-ok-50 px-4 py-3 text-sm text-ok-700">
                <CheckCircle2 className="h-4 w-4" /> Imported {formatNumber(totalRows)} rows from {result.filename}.
              </p>
              <div className="rounded-lg border border-border">
                <SheetCounts result={result} />
              </div>
              <div className="flex flex-col gap-2 rounded-lg border border-border bg-slate-50 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-700">
                  Run the network pipeline to refresh forecasts, safety stock targets and the transport plan with the new data.
                </p>
                {!runPipeline.isSuccess && (
                  <Button size="sm" onClick={() => runPipeline.mutate()} loading={runPipeline.isPending}>
                    <Play className="h-3.5 w-3.5" /> Run pipeline now
                  </Button>
                )}
                {runPipeline.isSuccess && (
                  <Link to={`/runs/${runPipeline.data.pipeline_run_id}`} className="text-sm font-medium text-brand-600 hover:text-brand-700">
                    Run started — view progress →
                  </Link>
                )}
              </div>
              {runPipeline.isError && <ErrorNotice message={errorMessage(runPipeline.error, 'Could not start the run')} />}
              <div>
                <Button variant="secondary" size="sm" onClick={startOver}>
                  Import another file
                </Button>
              </div>
            </div>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Import history" description="Every file that was imported, and by whom." />
        <CardBody className="overflow-x-auto p-0">
          {history.isLoading && <Spinner />}
          {history.isError && <div className="p-5"><ErrorNotice message={errorMessage(history.error, 'Failed to load history')} /></div>}
          {history.data && history.data.length === 0 && <EmptyState title="No imports yet" />}
          {history.data && history.data.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs uppercase tracking-wide text-muted">
                    <th className="px-5 py-2.5 font-medium">When</th>
                    <th className="px-5 py-2.5 font-medium">File</th>
                    <th className="px-5 py-2.5 font-medium">By</th>
                    <th className="px-5 py-2.5 font-medium">Changes</th>
                  </tr>
                </thead>
                <tbody>
                  {history.data.map((r) => (
                    <tr key={r.id} className="border-b border-border last:border-0">
                      <td className="whitespace-nowrap px-5 py-2.5 text-muted">{formatDateTime(r.created_at)}</td>
                      <td className="px-5 py-2.5 font-medium text-slate-900">{r.filename}</td>
                      <td className="px-5 py-2.5 text-muted">{r.user_email}</td>
                      <td className="px-5 py-2.5 text-xs text-slate-600">{summarize(r)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {can('admin') && <DemoDataCard />}

      <p className="text-xs text-muted">
        Tip: after an import, check <Badge tone="neutral">Policies</Badge> and <Badge tone="neutral">Network</Badge> to confirm the data looks right
        before running the pipeline.
      </p>
    </div>
  )
}
