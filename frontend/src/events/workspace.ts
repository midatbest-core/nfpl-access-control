export const WORKSPACE_REFRESH_EVENT = 'nfpl:workspace-refresh'

export function requestWorkspaceRefresh() {
  window.dispatchEvent(new Event(WORKSPACE_REFRESH_EVENT))
}
