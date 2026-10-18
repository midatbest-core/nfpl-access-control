import type { EmployeeProfile, RoleAssignment } from '../api/contracts'

export const ROLE = {
  admin: 'admin',
  maker: 'maker',
  checker: 'checker',
  filingOfficer: 'filing-officer',
  clientViewer: 'client-viewer',
  parserService: 'parser-service',
} as const

export function isRoleEffective(role: RoleAssignment, at = new Date()): boolean {
  const instant = at.getTime()
  return (
    Date.parse(role.valid_from) <= instant &&
    (role.valid_until === null || Date.parse(role.valid_until) > instant) &&
    (role.revoked_at === null || Date.parse(role.revoked_at) > instant)
  )
}

export function effectiveRoles(user: EmployeeProfile | null, at = new Date()): Set<string> {
  if (!user || user.account_status !== 'active') return new Set()
  return new Set(
    user.roles
      .filter((role) => isRoleEffective(role, at))
      .map((role) => role.role_slug)
  )
}

export function landingPath(user: EmployeeProfile): string {
  if (user.account_status !== 'active') {
    return '/account-status'
  }

  const roles = effectiveRoles(user)
  if (roles.has(ROLE.admin)) {
    return '/admin'
  }
  if (roles.has(ROLE.clientViewer)) {
    return '/client/shipments'
  }
  if (
    [ROLE.maker, ROLE.checker, ROLE.filingOfficer].some((role) =>
      roles.has(role)
    )
  ) {
    return '/work'
  }

  return '/unauthorized'
}
