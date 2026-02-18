const API_BASE = '/api/v1/catalog';

export const CatalogService = {
    async getCategories() {
        const resp = await fetch(`${API_BASE}/categories`);
        if (!resp.ok) throw new Error('Failed to fetch categories');
        return await resp.json();
    },

    async createCategory(payload) {
        const resp = await fetch(`${API_BASE}/categories`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error('Failed to create category');
        return await resp.json();
    },

    async deleteCategory(categoryId) {
        const resp = await fetch(`${API_BASE}/categories/${categoryId}`, {
            method: 'DELETE'
        });
        if (!resp.ok) throw new Error('Failed to delete category');
        return await resp.json();
    },

    async getProducts(categoryId = null) {
        let url = `${API_BASE}/products`;
        if (categoryId) url += `?category_id=${categoryId}`;
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Failed to fetch products');
        return await resp.json();
    },

    async getProduct(productId) {
        const resp = await fetch(`${API_BASE}/products/${productId}`);
        if (!resp.ok) throw new Error('Failed to fetch product');
        return await resp.json();
    },

    async createProduct(payload) {
        const resp = await fetch(`${API_BASE}/products`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error('Failed to create product');
        return await resp.json();
    },

    async updateProduct(productId, payload) {
        const resp = await fetch(`${API_BASE}/products/${productId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error('Failed to update product');
        return await resp.json();
    },

    async deleteProduct(productId) {
        const resp = await fetch(`${API_BASE}/products/${productId}`, {
            method: 'DELETE'
        });
        if (!resp.ok) throw new Error('Failed to delete product');
        return await resp.json();
    }
};
