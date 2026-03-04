<script setup>
import { ref, onMounted, computed } from 'vue'
import { CatalogService } from '../services/catalog'

// State
const categories = ref([])
const products = ref([])
const isLoading = ref(true)
const selectedCategory = ref(null)

// Form states
const showProductModal = ref(false)
const showCategoryModal = ref(false)
const isEditing = ref(false)
const currentProduct = ref({
  title: '',
  price: 0,
  description: '',
  image_url: '',
  attachment_url: '',
  category_id: null,
  details: {}
})
const currentCategory = ref({
  name: '',
  parent_id: null
})

const fetchAll = async () => {
  isLoading.value = true
  try {
    const [catData, prodData] = await Promise.all([
      CatalogService.getCategories(),
      CatalogService.getProducts(selectedCategory.value)
    ])
    categories.value = catData
    products.value = prodData
  } catch (err) {
    console.error(err)
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchAll)

const selectCategory = async (id) => {
  selectedCategory.value = id
  isLoading.value = true
  try {
    products.value = await CatalogService.getProducts(id)
  } catch (err) {
    console.error(err)
  } finally {
    isLoading.value = false
  }
}

const openProductModal = (product = null) => {
  if (product) {
    currentProduct.value = { ...product }
    isEditing.value = true
  } else {
    currentProduct.value = {
      title: '',
      price: 0,
      description: '',
      image_url: '',
      attachment_url: '',
      category_id: selectedCategory.value,
      details: {}
    }
    isEditing.value = false
  }
  showProductModal.value = true
}

const saveProduct = async () => {
  try {
    if (isEditing.value) {
      await CatalogService.updateProduct(currentProduct.value.id, currentProduct.value)
    } else {
      await CatalogService.createProduct(currentProduct.value)
    }
    showProductModal.value = false
    fetchAll()
  } catch (err) {
    alert(err.message)
  }
}

const deleteProduct = async (id) => {
  if (!confirm('Are you sure you want to delete this product?')) return
  try {
    await CatalogService.deleteProduct(id)
    fetchAll()
  } catch (err) {
    alert(err.message)
  }
}

const saveCategory = async () => {
    try {
        await CatalogService.createCategory(currentCategory.value)
        showCategoryModal.value = false
        currentCategory.value = { name: '', parent_id: null }
        fetchAll()
    } catch (err) {
        alert(err.message)
    }
}

const deleteCategory = async (id) => {
    if (!confirm('Are you sure? Products in this category will be orphaned.')) return
    try {
        await CatalogService.deleteCategory(id)
        if (selectedCategory.value === id) selectedCategory.value = null
        fetchAll()
    } catch (err) {
        alert(err.message)
    }
}

const getCategoryName = (id) => {
    const cat = categories.value.find(c => c.id === id)
    return cat ? cat.name : 'Uncategorized'
}
</script>

<template>
  <div class="flex flex-col h-[calc(100vh-64px)] w-full max-w-5xl mx-auto overflow-hidden bg-background-light dark:bg-background-dark text-slate-900 dark:text-slate-100 relative">
    
    <!-- TopAppBar & Header Area -->
    <header class="p-6 border-b border-slate-200 dark:border-slate-800 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md sticky top-0 z-30 shrink-0">
        <div class="flex justify-between items-end mb-4">
            <div class="flex items-center gap-4">
                <div class="size-12 rounded-2xl bg-primary/20 flex items-center justify-center text-primary border border-primary/20 shadow-sm relative overflow-hidden">
                    <span class="absolute inset-0 bg-primary/10 blur-xl"></span>
                    <span class="material-symbols-outlined relative z-10 text-2xl">category</span>
                </div>
                
                <div>
                    <h1 class="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Sales Catalog</h1>
                    <p class="text-[11px] text-primary font-bold uppercase tracking-widest mt-1">Products & Services Knowledge</p>
                </div>
            </div>
            
            <div class="flex gap-2">
                <button @click="showCategoryModal = true" class="h-10 w-10 shrink-0 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 shadow-sm hover:bg-slate-200 dark:hover:bg-slate-700 active:scale-95 transition-all relative">
                    <span class="material-symbols-outlined">folder</span>
                    <span class="absolute top-0 right-0 w-3.5 h-3.5 bg-primary rounded-full border-2 border-white dark:border-slate-900 text-[10px] font-black flex items-center justify-center text-white">+</span>
                </button>
                <button @click="openProductModal()" class="h-10 w-10 shrink-0 rounded-full bg-primary text-white shadow-lg shadow-primary/30 hover:bg-primary/90 active:scale-95 transition-all flex items-center justify-center">
                    <span class="material-symbols-outlined">add</span>
                </button>
            </div>
        </div>
        
        <!-- Mobile-First Horizontal Category Scroller -->
        <div class="flex items-center gap-2 overflow-x-auto scrollbar-none pb-1 -mx-2 px-2 snap-x">
            <button 
                @click="selectCategory(null)"
                class="snap-start shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-all border"
                :class="selectedCategory === null 
                    ? 'bg-primary text-white border-primary shadow-md shadow-primary/20' 
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700'"
            >
                All Products
            </button>
            <template v-for="cat in categories" :key="cat.id">
                <button 
                @click="selectCategory(cat.id)"
                class="snap-start shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-all border flex items-center gap-2 group"
                :class="selectedCategory === cat.id 
                    ? 'bg-primary text-white border-primary shadow-md shadow-primary/20' 
                    : 'bg-white dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700'"
                >
                {{ cat.name }}
                <span v-if="selectedCategory === cat.id" @click.stop="deleteCategory(cat.id)" class="text-white/80 hover:text-white hover:scale-110 ml-1 transition-transform">
                    <span class="material-symbols-outlined text-[14px]">cancel</span>
                </span>
                </button>
            </template>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 overflow-y-auto p-4 md:p-6 pb-24 scrollbar-none relative">
        <div v-if="isLoading" class="flex justify-center items-center py-20">
            <span class="material-symbols-outlined animate-spin text-4xl text-primary">sync</span>
        </div>

        <div v-else-if="products.length === 0" class="flex flex-col items-center justify-center h-full min-h-[400px] text-center bg-white dark:bg-slate-800 rounded-[2rem] border border-dashed border-slate-300 dark:border-slate-700">
            <div class="size-20 rounded-full bg-slate-50 dark:bg-slate-900 flex items-center justify-center mb-6">
                <span class="material-symbols-outlined text-4xl text-slate-400 dark:text-slate-500">inventory_2</span>
            </div>
            <h3 class="text-xl font-bold text-slate-900 dark:text-white mb-2">Configure Products</h3>
            <p class="text-sm text-slate-500 dark:text-slate-400 max-w-sm px-6">Add products or services to your catalog so passing AI agents can recommend them dynamically.</p>
            <button @click="openProductModal()" class="mt-6 font-bold bg-primary text-white px-6 py-3 rounded-full flex items-center gap-2 shadow-lg hover:shadow-primary/30 active:scale-95 transition-all w-fit mx-auto">
                <span class="material-symbols-outlined text-sm">add</span>
                Add First Entry
            </button>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div v-for="product in products" :key="product.id" class="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm rounded-3xl overflow-hidden flex flex-col group relative hover:shadow-lg transition-shadow">
                
                <!-- Image Box -->
                <div class="h-48 bg-slate-100 dark:bg-slate-900 relative overflow-hidden shrink-0">
                    <img v-if="product.image_url" :src="product.image_url" class="w-full h-full object-cover opacity-90 group-hover:opacity-100 group-hover:scale-105 transition-all duration-500" />
                    <div v-else class="w-full h-full flex items-center justify-center text-slate-400 dark:text-slate-600 bg-slate-50 dark:bg-slate-800">
                        <span class="material-symbols-outlined text-5xl">hide_image</span>
                    </div>

                    <!-- Price Badge -->
                    <div class="absolute top-4 right-4 bg-white/90 dark:bg-slate-900/90 backdrop-blur text-slate-900 dark:text-white font-black text-sm px-3 py-1.5 rounded-full shadow-sm border border-slate-200/50 dark:border-slate-700/50">
                        ${{ product.price }}
                    </div>

                    <!-- Quick Actions Overlays -->
                    <div class="absolute top-4 left-4 flex gap-2">
                        <button @click="openProductModal(product)" class="size-8 rounded-full bg-white/90 dark:bg-slate-900/90 backdrop-blur border border-slate-200/50 dark:border-slate-700/50 flex items-center justify-center text-slate-700 dark:text-slate-300 hover:text-primary active:scale-95 transition-transform">
                            <span class="material-symbols-outlined text-[16px]">edit</span>
                        </button>
                        <button @click="deleteProduct(product.id)" class="size-8 rounded-full bg-red-500/90 backdrop-blur border border-red-500/50 flex items-center justify-center text-white active:scale-95 transition-transform hover:bg-red-600">
                            <span class="material-symbols-outlined text-[16px]">delete</span>
                        </button>
                    </div>
                </div>

                <!-- Info Box -->
                <div class="p-5 flex-1 flex flex-col">
                    <span class="text-[10px] font-bold uppercase tracking-widest text-primary mb-2">
                        {{ getCategoryName(product.category_id) }}
                    </span>
                    <h3 class="font-bold text-slate-900 dark:text-white text-lg tracking-tight leading-snug mb-2">{{ product.title }}</h3>
                    <p class="text-sm text-slate-600 dark:text-slate-400 line-clamp-3 leading-relaxed flex-grow">{{ product.description || 'No description provided.' }}</p>

                    <div v-if="product.attachment_url" class="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700/50">
                        <a :href="product.attachment_url" target="_blank" class="flex items-center justify-center gap-2 w-full bg-slate-50 dark:bg-slate-800 rounded-xl py-2.5 text-xs font-bold text-primary border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
                            <span class="material-symbols-outlined text-[16px]">description</span>
                            Attached Material
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </main>

    <!-- Modals Overlay -->
    <div v-if="showProductModal || showCategoryModal" class="fixed inset-0 z-[100] flex items-end sm:items-center justify-center px-0 sm:px-4 pb-0 sm:pb-4">
        <div class="absolute inset-0 bg-slate-900/60 backdrop-blur-sm transition-opacity" @click="(showProductModal = false, showCategoryModal = false)"></div>
        
        <!-- PRODUCT MODAL -->
        <div v-if="showProductModal" class="w-full max-w-lg bg-white dark:bg-slate-900 sm:rounded-3xl rounded-t-3xl border border-slate-200 dark:border-slate-700 shadow-2xl flex flex-col relative z-10 animate-in slide-in-from-bottom max-h-[90vh]">
            <div class="p-5 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center bg-white/90 dark:bg-slate-900/90 backdrop-blur-md rounded-t-3xl shrink-0">
                <h2 class="text-lg font-bold text-slate-900 dark:text-white tracking-tight">{{ isEditing ? 'Edit Config' : 'New Entry' }}</h2>
                <button @click="showProductModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-full bg-slate-100 dark:bg-slate-800 transition-colors">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            
            <div class="p-5 overflow-y-auto space-y-5 scrollbar-none pb-safe">
                <div class="space-y-1.5 flex flex-col">
                    <label class="text-[10px] uppercase tracking-widest font-bold text-slate-600 dark:text-slate-400 pl-1">Product Title</label>
                    <input v-model="currentProduct.title" type="text" placeholder="e.g. Enterprise License" class="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none transition-shadow" />
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div class="space-y-1.5 flex flex-col">
                        <label class="text-[10px] uppercase tracking-widest font-bold text-slate-600 dark:text-slate-400 pl-1">Price ($)</label>
                        <div class="relative bg-slate-50 dark:bg-slate-800 rounded-2xl flex border-transparent focus-within:ring-2 focus-within:ring-primary transition-shadow">
                            <span class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 font-bold">$</span>
                            <input v-model="currentProduct.price" type="number" class="w-full bg-transparent border-none pl-8 pr-4 py-3 text-sm text-slate-900 dark:text-white outline-none" />
                        </div>
                    </div>
                    <div class="space-y-1.5 flex flex-col">
                        <label class="text-[10px] uppercase tracking-widest font-bold text-slate-600 dark:text-slate-400 pl-1">Category</label>
                        <select v-model="currentProduct.category_id" class="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none transition-shadow appearance-none">
                            <option :value="null">Uncategorized</option>
                            <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                        </select>
                    </div>
                </div>

                <div class="space-y-1.5 flex flex-col">
                    <label class="text-[10px] uppercase tracking-widest font-bold text-slate-600 dark:text-slate-400 pl-1">Description Logic</label>
                    <textarea v-model="currentProduct.description" rows="3" placeholder="Tell the AI what this is useful for..." class="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none transition-shadow resize-none"></textarea>
                </div>

                <div class="space-y-1.5 flex flex-col">
                    <label class="text-[10px] uppercase tracking-widest font-bold text-slate-600 dark:text-slate-400 pl-1">Cover Thumbnail URL</label>
                    <input v-model="currentProduct.image_url" type="text" placeholder="https://" class="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none transition-shadow" />
                </div>
                
                <div class="space-y-1.5 flex flex-col">
                    <label class="text-[10px] uppercase tracking-widest font-bold text-slate-600 dark:text-slate-400 pl-1">Detailed Link / Payload</label>
                    <input v-model="currentProduct.attachment_url" type="text" placeholder="https://..." class="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none transition-shadow" />
                </div>
            </div>

            <div class="p-5 border-t border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 shrink-0 mb-safe">
                <button @click="saveProduct" class="w-full bg-primary text-white shadow-lg hover:bg-primary/90 font-bold py-3.5 rounded-xl text-sm active:scale-[0.98] transition-all flex justify-center items-center gap-2">
                    <span class="material-symbols-outlined text-[18px]">save</span>
                    {{ isEditing ? 'Commit Changes' : 'Initialize Schema' }}
                </button>
            </div>
        </div>

        <!-- CATEGORY MODAL -->
        <div v-if="showCategoryModal" class="w-full max-w-sm bg-white dark:bg-slate-900 sm:rounded-3xl rounded-t-3xl border border-slate-200 dark:border-slate-700 shadow-2xl flex flex-col relative z-10 animate-in slide-in-from-bottom pb-safe">
            <div class="p-5 border-b border-slate-100 dark:border-slate-800 flex justify-between items-center rounded-t-3xl">
                <h2 class="text-lg font-bold text-slate-900 dark:text-white tracking-tight">Add Collection</h2>
                <button @click="showCategoryModal = false" class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-1 rounded-full bg-slate-100 dark:bg-slate-800 transition-colors">
                    <span class="material-symbols-outlined">close</span>
                </button>
            </div>
            
            <div class="p-5 space-y-5">
                <div class="space-y-1.5 flex flex-col">
                    <label class="text-[10px] uppercase tracking-widest font-bold text-slate-600 dark:text-slate-400 pl-1">Category Tag</label>
                    <input v-model="currentCategory.name" type="text" placeholder="e.g. Services" class="w-full bg-slate-50 dark:bg-slate-800 border-none rounded-2xl px-4 py-3 text-sm text-slate-900 dark:text-white focus:ring-2 focus:ring-primary outline-none transition-shadow" />
                </div>
            </div>

            <div class="p-5 border-t border-slate-100 dark:border-slate-800">
                <button @click="saveCategory" class="w-full bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-bold py-3.5 rounded-xl text-sm shadow-md active:scale-[0.98] transition-all flex justify-center items-center gap-2">
                    Create Set
                </button>
            </div>
        </div>

    </div>
  </div>
</template>

<style scoped>
.scrollbar-none::-webkit-scrollbar {
  display: none;
}
.scrollbar-none {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
/* Basic safe padding utility for mobile keyboards/notches */
.pb-safe {
    padding-bottom: env(safe-area-inset-bottom, 1rem); 
}
.mb-safe {
    margin-bottom: env(safe-area-inset-bottom, 0); 
}
</style>
