import { request } from './api'

export const CatalogService = {
    async getCategories() {
        return request('/catalog/categories')
    },

    async createCategory(payload) {
        return request('/catalog/categories', {
            method: 'POST',
            body: JSON.stringify(payload)
        })
    },

    async deleteCategory(categoryId) {
        return request(`/catalog/categories/${categoryId}`, {
            method: 'DELETE'
        })
    },

    async getProducts(categoryId = null) {
        let path = '/catalog/products'
        if (categoryId) path += `?category_id=${categoryId}`
        return request(path)
    },

    async getProduct(productId) {
        return request(`/catalog/products/${productId}`)
    },

    async createProduct(payload) {
        return request('/catalog/products', {
            method: 'POST',
            body: JSON.stringify(payload)
        })
    },

    async updateProduct(productId, payload) {
        return request(`/catalog/products/${productId}`, {
            method: 'PUT',
            body: JSON.stringify(payload)
        })
    },

    async deleteProduct(productId) {
        return request(`/catalog/products/${productId}`, {
            method: 'DELETE'
        })
    }
}
