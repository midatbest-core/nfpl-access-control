import {
  AirIcon,
  FileCheckIcon,
  LayersIcon,
  ShieldCheckIcon,
  UserIcon,
} from '../../components/icons'

export interface DemoAccount {
  role: string
  email: string
  name: string
  badge: string
  scope: string
  icon: typeof LayersIcon
  tone: string
  keyTest: string
}

export const DEMO_EVALUATION_ACCOUNTS: DemoAccount[] = [
  {
    role: 'Global Admin',
    email: 'admin@nfpl.test',
    name: 'Nadia Admin',
    badge: 'Operations Command',
    scope: 'Full administrative authority across all clients, branches, directions, and modes.',
    icon: LayersIcon,
    tone: 'border-cyan-200 bg-cyan-50/50 text-cyan-900',
    keyTest: 'Admin dashboard KPIs, create shipment, assignment suggestions, urgent requests, and full audit history timeline.',
  },
  {
    role: 'Maker (Global)',
    email: 'emp-00@nfpl.test',
    name: 'Aarav Shah',
    badge: 'Maker / Checker',
    scope: 'Global Maker; Checker for CL001. Has approved temporary absence history.',
    icon: FileCheckIcon,
    tone: 'border-sky-200 bg-sky-50/50 text-sky-900',
    keyTest: 'My Work queue search, shipment drafting, prepare/submit with justification, and edit request creation.',
  },
  {
    role: 'Checker & Filing Officer',
    email: 'emp-01@nfpl.test',
    name: 'Diya Nair',
    badge: 'Scoped Checker',
    scope: 'Checker for CL001 + BR01 + Import; Filing Officer for BR02.',
    icon: ShieldCheckIcon,
    tone: 'border-violet-200 bg-violet-50/50 text-violet-900',
    keyTest: 'Dynamic verification checklist items (Complete/Incomplete/N/A), justified N/A, and return for correction.',
  },
  {
    role: 'Global Filing Officer',
    email: 'emp-02@nfpl.test',
    name: 'Kabir Rao',
    badge: 'Filing Officer',
    scope: 'Filing Officer across all branches, modes, and directions.',
    icon: FileCheckIcon,
    tone: 'border-emerald-200 bg-emerald-50/50 text-emerald-900',
    keyTest: 'Final shipment filing and return for correction with category (Maker/Checker/Both) & mandatory reason.',
  },
  {
    role: 'Client Viewer',
    email: 'client-viewer-00@portal.test',
    name: 'Acme Logistics Viewer',
    badge: 'External Client',
    scope: 'Restricted strictly to CL001 shipments. Sanitized read-only status, milestones, and feed.',
    icon: AirIcon,
    tone: 'border-slate-200 bg-slate-50/80 text-slate-800',
    keyTest: 'Progress bar, sanitized milestone history feed (no staff identities), and direct Admin inquiries.',
  },
  {
    role: 'Disabled Employee',
    email: 'emp-18@nfpl.test',
    name: 'Krish Banerjee',
    badge: 'Disabled Account',
    scope: 'Account deactivated by Admin. Authentication and protected routes fail immediately.',
    icon: UserIcon,
    tone: 'border-rose-200 bg-rose-50/50 text-rose-900',
    keyTest: 'Verify fail-closed security invariant: login is immediately rejected without issuing session token.',
  },
]
