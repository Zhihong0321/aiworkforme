export const normalizeChannelStatus = (status) => String(status || '').trim().toLowerCase()

export const isConnectedChannelStatus = (status) =>
  ['connected', 'active', 'live', 'ready', 'open'].includes(normalizeChannelStatus(status))

export const getChannelDescription = (session) => session?.session_metadata?.description || ''

export const getConnectedNumber = (session) =>
  session?.session_metadata?.connected_number
  || session?.session_metadata?.phone_number
  || session?.session_metadata?.phone
  || ''

export const getProviderSessionId = (session) =>
  session?.session_metadata?.provider_session_id
  || session?.session_identifier
  || 'Unavailable'

export const getChannelIdentity = (session) => {
  const connectedNumber = getConnectedNumber(session)
  if (connectedNumber) return connectedNumber

  const sessionIdentifier = String(session?.session_identifier || '').trim()
  if (/^\d{8,15}$/.test(sessionIdentifier)) return sessionIdentifier

  const displayName = String(session?.display_name || '').trim()
  if (/^\d{8,15}$/.test(displayName)) return displayName

  return displayName || sessionIdentifier || 'Pending identity'
}

export const getChannelBadgeLabel = (session) => {
  if (!session) return 'Unassigned'
  return isConnectedChannelStatus(session.status) ? 'Connected' : 'Needs setup'
}
