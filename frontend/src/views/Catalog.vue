<script setup>
import { ref, onMounted, computed } from 'vue'
import { CatalogService } from '../services/catalog'
import TuiButton from '../components/ui/TuiButton.vue'
import TuiCard from '../components/ui/TuiCard.vue'
import TuiInput from '../components/ui/TuiInput.vue'
import TuiSelect from '../components/ui/TuiSelect.vue'
import TuiBadge from '../components/ui/TuiBadge.vue'
import TuiLoader from '../components/ui/TuiLoader.vue'
import TuiScrambleTitle from '../components/ui/TuiScrambleTitle.vue'
import { useTheme } from '../composables/theme'

const { theme } = useTheme()
const isDark = computed(() => theme.value === 'dark')

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
  isLoading.ref = true
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

// Hierarchy helper
const rootCategories = computed(() => categories.value.filter(c => !c.parent_id))
const subCategories = (parentId) => categories.value.filter(c => c.parent_id === parentId)

</script>

<template>
  <div class="p-6 max-w-7xl mx-auto min-h-screen">
    <div class="flex justify-between items-center mb-8">
      <div>
        <TuiScrambleTitle text="PRODUCT CATALOG" class="text-3xl font-black tracking-tighter" />
        <p class="text-slate-500 text-xs mt-1 uppercase tracking-widest font-bold">Manage your store inventory for AI Agents</p>
      </div>
      <div class="flex gap-3">
        <TuiButton @click="showCategoryModal = true" variant="secondary">Add Category</TuiButton>
        <TuiButton @click="openProductModal()">Add Product</TuiButton>
      </div>
    </div>

    <div class="grid grid-cols-12 gap-8">
      <!-- Sidebar Categories -->
      <div class="col-span-12 lg:col-span-3">
        <div :class="['rounded-xl border p-4 sticky top-24', isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
          <h3 class="text-[10px] font-black uppercase tracking-widest mb-4 text-slate-400">Categories</h3>
          
          <div class="space-y-1">
            <button 
              @click="selectCategory(null)"
              :class="['w-full text-left px-3 py-2 rounded-lg text-xs font-bold transition-all', 
                selectedCategory === null ? 'bg-black text-white' : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500']"
            >
              ALL PRODUCTS
            </button>

            <div v-for="root in rootCategories" :key="root.id">
              <div class="flex items-center group">
                <button 
                  @click="selectCategory(root.id)"
                  :class="['flex-1 text-left px-3 py-2 rounded-lg text-xs font-bold transition-all', 
                    selectedCategory === root.id ? 'bg-black text-white' : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-500']"
                >
                  {{ root.name }}
                </button>
                <button @click="deleteCategory(root.id)" class="opacity-0 group-hover:opacity-100 p-2 text-red-500 hover:scale-110 transition-all">
                    <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                </button>
              </div>
              
              <div v-for="sub in subCategories(root.id)" :key="sub.id" class="ml-4 mt-1 border-l pl-2 border-slate-200 dark:border-slate-800">
                <div class="flex items-center group">
                  <button 
                    @click="selectCategory(sub.id)"
                    :class="['flex-1 text-left px-3 py-1.5 rounded-lg text-[11px] font-medium transition-all', 
                      selectedCategory === sub.id ? 'bg-black text-white' : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400']"
                  >
                    {{ sub.name }}
                  </button>
                  <button @click="deleteCategory(sub.id)" class="opacity-0 group-hover:opacity-100 p-2 text-red-500 hover:scale-110 transition-all">
                      <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Main Content -->
      <div class="col-span-12 lg:col-span-9">
        <div v-if="isLoading" class="flex justify-center items-center py-20">
          <TuiLoader />
        </div>

        <div v-else-if="products.length === 0" class="text-center py-20 border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-2xl">
          <div class="text-slate-300 mb-4">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" /></svg>
          </div>
          <h4 class="text-slate-500 font-bold uppercase tracking-widest">No products found</h4>
          <TuiButton @click="openProductModal()" variant="secondary" class="mt-4">Create your first product</TuiButton>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          <TuiCard v-for="product in products" :key="product.id" class="group overflow-hidden flex flex-col">
            <div class="h-48 bg-slate-100 dark:bg-slate-800 relative overflow-hidden">
               <img v-if="product.image_url" :src="product.image_url" class="w-full h-full object-cover group-hover:scale-110 transition-transform duration-700" />
               <div v-else class="w-full h-full flex items-center justify-center text-slate-300">
                 <svg xmlns="http://www.w3.org/2000/svg" class="h-12 w-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
               </div>
               <div class="absolute top-2 right-2">
                 <TuiBadge :text="`$${product.price}`" variant="success" />
               </div>
            </div>

            <div class="p-5 flex-1 flex flex-col">
              <div class="flex justify-between items-start mb-2">
                <h4 class="font-black text-lg tracking-tight leading-none">{{ product.title }}</h4>
                <div class="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button @click="openProductModal(product)" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-800 rounded">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                    </button>
                    <button @click="deleteProduct(product.id)" class="p-1.5 hover:bg-red-50 text-red-500 rounded">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                    </button>
                </div>
              </div>
              <p class="text-slate-500 text-xs mb-4 line-clamp-2">{{ product.description }}</p>
              
              <div class="mt-auto flex items-center justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
                <span class="text-[9px] font-bold uppercase tracking-widest text-slate-400">
                  {{ getCategoryName(product.category_id) }}
                </span>
                <a v-if="product.attachment_url" :href="product.attachment_url" target="_blank" class="text-[9px] font-black uppercase text-blue-500 hover:underline">
                  View Attachment
                </a>
              </div>
            </div>
          </TuiCard>
        </div>
      </div>
    </div>

    <!-- Product Modal -->
    <div v-if="showProductModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm" @click="showProductModal = false"></div>
      <div :class="['relative w-full max-w-lg rounded-2xl shadow-2xl p-8 border', isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
        <h2 class="text-2xl font-black mb-6 tracking-tight uppercase">{{ isEditing ? 'Update Product' : 'Create Product' }}</h2>
        
        <div class="space-y-4">
          <TuiInput v-model="currentProduct.title" label="Title" placeholder="High efficiency solar panel..." />
          <div class="grid grid-cols-2 gap-4">
            <TuiInput v-model="currentProduct.price" type="number" label="Price ($)" />
            <TuiSelect 
                v-model="currentProduct.category_id" 
                label="Category" 
                :options="categories.map(c => ({ label: c.name, value: c.id }))" 
            />
          </div>
          <div>
            <label class="block text-[10px] font-bold uppercase tracking-widest text-slate-400 mb-1">Description</label>
            <textarea 
                v-model="currentProduct.description" 
                rows="3" 
                :class="['w-full rounded-lg border px-3 py-2 text-sm focus:ring-1 focus:outline-none', 
                  isDark ? 'bg-slate-800 border-slate-700 text-white focus:ring-slate-600' : 'bg-slate-50 border-slate-200 text-slate-900 focus:ring-black']"
            ></textarea>
          </div>
          <TuiInput v-model="currentProduct.image_url" label="Image URL" placeholder="https://..." />
          <TuiInput v-model="currentProduct.attachment_url" label="Attachment URL (PDF/DOC)" placeholder="https://..." />
        </div>

        <div class="flex gap-3 mt-8">
          <TuiButton @click="showProductModal = false" variant="secondary" class="flex-1">Cancel</TuiButton>
          <TuiButton @click="saveProduct" class="flex-1">{{ isEditing ? 'Update' : 'Create' }}</TuiButton>
        </div>
      </div>
    </div>

    <!-- Category Modal -->
    <div v-if="showCategoryModal" class="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div class="absolute inset-0 bg-slate-900/80 backdrop-blur-sm" @click="showCategoryModal = false"></div>
      <div :class="['relative w-full max-w-sm rounded-2xl shadow-2xl p-8 border', isDark ? 'bg-slate-900 border-slate-800' : 'bg-white border-slate-200']">
        <h2 class="text-2xl font-black mb-6 tracking-tight uppercase">New Category</h2>
        <div class="space-y-4">
          <TuiInput v-model="currentCategory.name" label="Category Name" placeholder="Electronics..." />
          <TuiSelect 
              v-model="currentCategory.parent_id" 
              label="Parent Category (Optional)" 
              :options="[{label: 'None', value: null}, ...rootCategories.map(c => ({ label: c.name, value: c.id }))]" 
          />
        </div>
        <div class="flex gap-3 mt-8">
          <TuiButton @click="showCategoryModal = false" variant="secondary" class="flex-1">Cancel</TuiButton>
          <TuiButton @click="saveCategory" class="flex-1">Create</TuiButton>
        </div>
      </div>
    </div>

  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;  
  overflow: hidden;
}
</style>
