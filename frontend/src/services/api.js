import { store } from '../store'

const API_BASE = `${window.location.origin}/api/v1`
const DEFAULT_REQUEST_TIMEOUT_MS = 15000

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

    const controller = new AbortController()
    const timeoutMs = Number(options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS)
    const timeoutId = Number.isFinite(timeoutMs) && timeoutMs > 0
        ? window.setTimeout(() => controller.abort(), timeoutMs)
        : null

    let response
    try {
        response = await fetch(url, {
            ...options,
            headers,
            signal: options.signal ?? controller.signal,
        })
    } catch (error) {
        if (error?.name === 'AbortError') {
            throw new Error('Request timed out')
        }
        throw error
    } finally {
        if (timeoutId !== null) {
            window.clearTimeout(timeoutId)
        }
    }

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

    const text = await response.text();
    return text ? JSON.parse(text) : null;
}
