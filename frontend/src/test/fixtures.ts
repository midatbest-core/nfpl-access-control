import type { EmployeeProfile, RoleAssignment } from '../api/contracts'

export function role(roleSlug: string, overrides: Partial<RoleAssignment> = {}): RoleAssignment {
  return {
    id: `role-${roleSlug}`,
    role_slug: roleSlug,
    all_clients: true,
    client_id: null,
    all_branches: true,
    branch_id: null,
    all_directions: true,
    direction: null,
    all_modes: true,
    mode: null,
    valid_from: '2025-01-01T00:00:00Z',
    valid_until: null,
    revoked_at: null,
    ...overrides,
  }
}

export function profile(
  roleSlugs: string[] = ['maker'],
  overrides: Partial<EmployeeProfile> = {},
): EmployeeProfile {
  return {
    id: 'user-1',
    email: 'employee@nfpl.example',
    display_name: 'Morgan Lee',
    kind: 'staff',
    branch_id: 'branch-1',
    branch_name: 'Main Branch',
    account_status: 'active',
    availability: 'available',
    pending_workload: 3,
    roles: roleSlugs.map((slug) => role(slug)),
    created_at: '2025-01-01T00:00:00Z',
    ...overrides,
  }
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
