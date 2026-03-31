import { request } from './api'
import { store } from '../store'

const withAgentQuery = (basePath, extraParams = {}) => {
    const params = new URLSearchParams()
    const activeAgentId = Number(store.activeAgentId || 0)
    if (activeAgentId) {
        params.set('agent_id', String(activeAgentId))
    }
    for (const [key, value] of Object.entries(extraParams)) {
        if (value === null || value === undefined || value === '') continue
        params.set(key, String(value))
    }
    const query = params.toString()
    return query ? `${basePath}?${query}` : basePath
}

export const calendarService = {
    async getConfig() {
        return request(withAgentQuery('/calendar/config'))
    },

    async updateConfig(config) {
        return request(withAgentQuery('/calendar/config'), {
            method: 'POST',
            body: JSON.stringify(config),
        })
    },

    async getEvents(start, end) {
        return request(withAgentQuery('/calendar/events', {
            start: start ? start.toISOString() : null,
            end: end ? end.toISOString() : null,
        }))
    },

    async createEvent(event) {
        return request(withAgentQuery('/calendar/events'), {
            method: 'POST',
            body: JSON.stringify(event),
        })
    },

    async deleteEvent(eventId) {
        return request(withAgentQuery(`/calendar/events/${eventId}`), {
            method: 'DELETE',
        })
    },

    async getAvailability(date, durationMinutes = 30) {
        return request(withAgentQuery('/calendar/availability', {
            date: date.toISOString(),
            duration_minutes: durationMinutes,
        }))
    },
}
