import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { FormField, TextInput } from '../../components/design-system/FormElements'
import { useToast } from '../../components/feedback/ToastContext'
import {
  AnchorIcon,
  ArrowRightIcon,
  BuildingIcon,
  CheckCircleIcon,
  LockIcon,
  UserIcon,
} from '../../components/icons'

export function RegisterPage() {
  const navigate = useNavigate()
  const toast = useToast()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [branchId, setBranchId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [registeredSuccess, setRegisteredSuccess] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim() || !email.trim() || !password || !branchId.trim()) {
      setErrorMessage('Please fill in all required fields.')
      return
    }

    setSubmitting(true)
    setErrorMessage(null)

    try {
      await api.register({
        name: name.trim(),
        email: email.trim(),
        password,
        branch_id: branchId.trim(),
      })
      setRegisteredSuccess(true)
      toast.success('Registration submitted for administrator approval', 'Account Created')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Registration failed. Please try again.'
      setErrorMessage(msg)
      toast.error(msg, 'Registration Error')
    } finally {
      setSubmitting(false)
    }
  }

  if (registeredSuccess) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-50 p-4">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-lg space-y-4">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-emerald-50 text-emerald-600">
            <CheckCircleIcon className="h-8 w-8" />
          </div>
          <h2 className="text-xl font-bold text-slate-900">Registration Submitted</h2>
          <p className="text-sm text-slate-600 leading-relaxed">
            Your staff account has been created with <strong className="font-semibold text-slate-800">Pending</strong> status. An administrator must approve your account and assign your operational scope before you can access shipments.
          </p>
          <div className="pt-4">
            <button
              type="button"
              onClick={() => navigate('/login')}
              className="inline-flex w-full items-center justify-center rounded-xl bg-maritime-800 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-maritime-900 transition"
            >
              Return to Sign In
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl bg-maritime-800 text-white shadow-md">
            <AnchorIcon className="h-6 w-6 text-cyan-400" />
          </div>
          <h1 className="mt-4 text-2xl font-bold tracking-tight text-slate-900">
            Register NFPL staff account
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            All registrations enter pending administrative review. Roles are never self-granted.
          </p>
        </div>

        {errorMessage && (
          <div
            className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs font-semibold text-rose-800"
            role="alert"
          >
            {errorMessage}
          </div>
        )}

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <form onSubmit={handleSubmit} noValidate className="space-y-4">
            <FormField id="reg-name" label="Full Name" required>
              <TextInput
                id="reg-name"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Morgan Lee"
                icon={<UserIcon className="h-4 w-4" />}
              />
            </FormField>

            <FormField id="reg-email" label="Work Email" required>
              <TextInput
                id="reg-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="morgan.lee@nfpl.test"
                icon={<UserIcon className="h-4 w-4" />}
              />
            </FormField>

            <FormField id="reg-branch" label="Branch ID or Code" required helperText="Enter your assigned branch identifier (e.g. BR01, HQ)">
              <TextInput
                id="reg-branch"
                type="text"
                required
                value={branchId}
                onChange={(e) => setBranchId(e.target.value)}
                placeholder="BR01"
                icon={<BuildingIcon className="h-4 w-4" />}
              />
            </FormField>

            <FormField id="reg-password" label="Password" required helperText="Minimum 8 characters">
              <TextInput
                id="reg-password"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                icon={<LockIcon className="h-4 w-4" />}
              />
            </FormField>

            <button
              type="submit"
              disabled={submitting}
              className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-maritime-800 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-maritime-900 focus-visible:outline-2 disabled:opacity-50"
            >
              {submitting ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
                  Submitting registration...
                </>
              ) : (
                <>
                  Submit for approval
                  <ArrowRightIcon className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-xs text-slate-500">
            Already have an active account?{' '}
            <Link to="/login" className="font-semibold text-cyan-700 hover:text-cyan-800">
              Sign in here
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
