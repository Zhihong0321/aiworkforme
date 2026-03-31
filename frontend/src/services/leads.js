import { request } from './api'

export const LeadsService = {
    async deleteLeadPermanently(leadId) {
        return request(`/leads/${leadId}`, {
            method: 'DELETE'
        })
    }
}
