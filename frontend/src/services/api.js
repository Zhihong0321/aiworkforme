import { store } from '../store'

const API_BASE = `${window.location.origin}/api/v1`

export async function request(path, options = {}) {
    // Determine the full URL
    const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? path : '/' + path}`

    // Default headers
    const headers = {
        ...options.headers
    }

    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json'
    }

    // Add Authorization if token exists
    const token = localStorage.getItem('token')
    if (token) {
        headers['Authorization'] = `Bearer ${token}`
    }

    // Add Tenant ID if available
    const tenantIdRaw = localStorage.getItem('tenant_id') ?? store.activeWorkspace?.tenant_id
    const tenantIdStr = tenantIdRaw === null || tenantIdRaw === undefined ? '' : String(tenantIdRaw).trim()
    if (tenantIdStr && tenantIdStr !== 'null' && tenantIdStr !== 'undefined' && /^\d+$/.test(tenantIdStr)) {
        headers['X-Tenant-Id'] = tenantIdStr
    }

    const response = await fetch(url, {
        ...options,
        headers
    })

    if (response.status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('tenant_id')
        localStorage.removeItem('user_id')
        localStorage.removeItem('is_platform_admin')
        throw new Error('Unauthorized')
    }

    if (!response.ok) {
        let errorDetail = 'Request failed'
        try {
            const err = await response.json()
            errorDetail = err.detail || err.message || errorDetail
        } catch (e) {
            // Not JSON
        }
        throw new Error(errorDetail)
    }

    return response.json()
}
