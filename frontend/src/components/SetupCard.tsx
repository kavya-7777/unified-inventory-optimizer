import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { Database, FileSpreadsheet, Rocket } from 'lucide-react'
import { api, ApiError } from '@/lib/api'
import { useAuth } from '@/lib/auth-context'
import { Button } from '@/components/ui/Button'
import { Card, CardBody } from '@/components/ui/Card'
import { ErrorNotice } from '@/components/ui/Feedback'

/** First-run screen: shown on the dashboard until the database holds any policies. */
export function SetupCard() {
  const { can } = useAuth()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const loadDemo = useMutation({
    mutationFn: async () => {
      await api.loadDemoData(false)
      return api.runNetwork({})
    },
    onSuccess: (run) => {
      queryClient.invalidateQueries()
      navigate(`/runs/${run.pipeline_run_id}`)
    },
  })

  return (
    <Card className="overflow-hidden">
      <CardBody className="flex flex-col gap-6 px-6 py-8 sm:px-10">
        <div className="flex flex-col gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
            <Rocket className="h-5 w-5" />
          </div>
          <h2 className="text-lg font-semibold text-slate-900">Welcome! Let’s get some data in</h2>
          <p className="max-w-2xl text-sm text-muted">
            The optimizer needs your network (locations, SKUs, lanes), inventory policies, current stock and daily sales
            history. Import your own from Excel, or load the demo network to explore first.
          </p>
        </div>

        {can('planner') ? (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-3 rounded-xl border border-border p-5">
              <FileSpreadsheet className="h-5 w-5 text-ok-600" />
              <div>
                <p className="font-medium text-slate-900">Import your data</p>
                <p className="mt-1 text-sm text-muted">Download the Excel template, fill it in and upload it. Every row is checked first.</p>
              </div>
              <Link to="/import" className="mt-auto">
                <Button variant="secondary" className="w-full">Go to Data Import</Button>
              </Link>
            </div>
            {can('admin') && (
              <div className="flex flex-col gap-3 rounded-xl border border-border p-5">
                <Database className="h-5 w-5 text-brand-600" />
                <div>
                  <p className="font-medium text-slate-900">Load the demo network</p>
                  <p className="mt-1 text-sm text-muted">
                    5 suppliers, 3 DCs and 20 stores across South India, 50 SKUs and 120 days of sales. Then runs the pipeline.
                  </p>
                </div>
                <Button className="mt-auto w-full" onClick={() => loadDemo.mutate()} loading={loadDemo.isPending}>
                  {loadDemo.isPending ? 'Loading demo data…' : 'Load demo data'}
                </Button>
                {loadDemo.isError && (
                  <ErrorNotice message={loadDemo.error instanceof ApiError ? loadDemo.error.message : 'Loading demo data failed'} />
                )}
              </div>
            )}
          </div>
        ) : (
          <p className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700">
            No data has been loaded yet. Ask an admin or planner to import your company’s data — dashboards fill in automatically after
            the first pipeline run.
          </p>
        )}
      </CardBody>
    </Card>
  )
}
