import { request } from './api'

export const calendarService = {
    async getConfig() {
        return request('/calendar/config')
    },

    async updateConfig(config) {
        return request('/calendar/config', {
            method: 'POST',
            body: JSON.stringify(config),
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
            body: JSON.stringify(event),
        })
    },

    async deleteEvent(eventId) {
        return request(`/calendar/events/${eventId}`, {
            method: 'DELETE',
        })
    },

    async getAvailability(date, durationMinutes = 30) {
        return request(`/calendar/availability?date=${date.toISOString()}&duration_minutes=${durationMinutes}`)
    },
}
