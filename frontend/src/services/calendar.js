import { store } from '../store'

const API_BASE = (import.meta.env.VITE_API_BASE || 'http://localhost:8000/api/v1').replace(/\/$/, '')

async function request(path, options = {}) {
    const url = `${API_BASE}${path}`
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('token')}`,
        'X-Tenant-Id': store.activeWorkspace?.tenant_id || ''
    }

    const response = await fetch(url, {
        ...options,
        headers: { ...headers, ...options.headers }
    })

    if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || 'Request failed')
    }

    return response.json()
}

export const calendarService = {
    async getConfig() {
        return request('/calendar/config')
    },

    async updateConfig(config) {
        return request('/calendar/config', {
            method: 'POST',
            body: JSON.stringify(config)
        })
    },

    async getEvents(start, end) {
        let query = ''
        if (start && end) {
            query = `?start=${start.toISOString()}&end=${end.toISOString()}`
        }
        return request(`/calendar/events${query}`)
    },

    async createEvent(event) {
        return request('/calendar/events', {
            method: 'POST',
            body: JSON.stringify(event)
        })
    },

    async deleteEvent(eventId) {
        return request(`/calendar/events/${eventId}`, {
            method: 'DELETE'
        })
    },

    async getAvailability(date, durationMinutes = 30) {
        return request(`/calendar/availability?date=${date.toISOString()}&duration_minutes=${durationMinutes}`)
    }
}
