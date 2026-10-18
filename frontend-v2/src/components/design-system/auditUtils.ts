export type AuditCategory =
  | 'workflow'
  | 'access'
  | 'responsibility'
  | 'exception'
  | 'security'

export function classifyAuditAction(action: string): AuditCategory {
  const norm = action.toLowerCase()

  if (
    norm.includes('prepare') ||
    norm.includes('check') ||
    norm.includes('file') ||
    norm.includes('return') ||
    norm.includes('create_job') ||
    norm.includes('update_job')
  ) {
    return 'workflow'
  }

  if (
    norm.includes('role') ||
    norm.includes('grant') ||
    norm.includes('revoke') ||
    norm.includes('permission')
  ) {
    return 'access'
  }

  if (
    norm.includes('assign') ||
    norm.includes('delegate') ||
    norm.includes('absence') ||
    norm.includes('nomination')
  ) {
    return 'responsibility'
  }

  if (
    norm.includes('exception') ||
    norm.includes('edit_request') ||
    norm.includes('override') ||
    norm.includes('cancel') ||
    norm.includes('reopen') ||
    norm.includes('archive')
  ) {
    return 'exception'
  }

  return 'security'
}
