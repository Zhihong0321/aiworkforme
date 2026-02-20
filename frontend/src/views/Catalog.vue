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
  <div class="min-h-[calc(100vh-64px)] w-full bg-onyx font-inter text-slate-200 pb-20 relative overflow-hidden flex flex-col">
    <!-- Aurora Background Effect -->
    <div class="absolute inset-0 bg-mobile-aurora z-0 pointer-events-none opacity-40"></div>

    <!-- Header Section -->
    <div class="p-5 border-b border-slate-800/50 glass-panel-light rounded-b-[2rem] sticky top-0 z-30 mb-2 relative">
       <div class="flex justify-between items-end">
         <div>
           <h1 class="text-3xl font-semibold text-white tracking-tight mb-1">Catalog</h1>
           <p class="text-[10px] text-aurora font-bold uppercase tracking-widest mt-1">Manage Sales Inventory</p>
         </div>
         <div class="flex gap-2">
            <button @click="showCategoryModal = true" class="h-10 w-10 shrink-0 rounded-full bg-slate-800 flex items-center justify-center text-slate-300 border border-slate-700 shadow-lg active:scale-95 transition-all">
               <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" /></svg>
               <span class="absolute top-0 right-0 w-3 h-3 bg-indigo-500 rounded-full border-2 border-slate-800 text-[8px] flex items-center justify-center text-white">+</span>
            </button>
            <button @click="openProductModal()" class="h-10 w-10 shrink-0 rounded-full bg-aurora-gradient flex items-center justify-center text-white shadow-lg shadow-purple-500/20 active:scale-95 transition-all">
               <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
            </button>
         </div>
       </div>

       <!-- Mobile-First Horizontal Category Scroller -->
       <div class="mt-6 -mx-5 px-5 overflow-x-auto scrollbar-none pb-2 flex items-center gap-2 snap-x">
          <button 
            @click="selectCategory(null)"
            class="snap-start shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-all border"
            :class="selectedCategory === null ? 'bg-white text-slate-900 border-white shadow-[0_0_15px_rgba(255,255,255,0.3)]' : 'bg-slate-900/50 text-slate-400 border-slate-700/50 hover:bg-slate-800'"
          >
            All Products
          </button>
          
          <template v-for="cat in categories" :key="cat.id">
            <button 
              @click="selectCategory(cat.id)"
              class="snap-start shrink-0 px-4 py-2 rounded-full text-xs font-bold transition-all border flex items-center gap-2 group"
              :class="selectedCategory === cat.id ? 'bg-white text-slate-900 border-white shadow-[0_0_15px_rgba(255,255,255,0.3)]' : 'bg-slate-900/50 text-slate-400 border-slate-700/50 hover:bg-slate-800'"
            >
              {{ cat.name }}
              <span v-if="selectedCategory === cat.id" @click.stop="deleteCategory(cat.id)" class="text-red-500 hover:scale-110 ml-1">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
              </span>
            </button>
          </template>
       </div>
    </div>

    <!-- Main Content Area -->
    <div class="flex-grow px-4 pb-10 relative z-10 w-full max-w-5xl mx-auto">
      
      <!-- Loading State -->
      <div v-if="isLoading" class="flex justify-center items-center py-20">
         <div class="w-8 h-8 border-4 border-purple-500/30 border-t-purple-500 rounded-full animate-spin"></div>
      </div>

      <!-- Empty State -->
      <div v-else-if="products.length === 0" class="mt-10 glass-panel border-dashed border-slate-600 rounded-[2rem] p-8 text-center flex flex-col items-center justify-center">
         <div class="w-16 h-16 rounded-full bg-slate-800/50 flex items-center justify-center mb-4 border border-slate-700">
             <svg class="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
         </div>
         <h4 class="text-white font-bold tracking-tight mb-2">No Products Configured</h4>
         <p class="text-xs text-slate-400 max-w-xs leading-relaxed mb-6">Add products or services here so your AI Agents can reference them when talking to customers.</p>
         <button @click="openProductModal()" class="bg-white text-slate-900 font-bold text-sm px-6 py-3 rounded-xl shadow-lg active:scale-95 transition-transform">
            Add First Product
         </button>
      </div>

      <!-- Product List (Mobile: Stacked, Desktop: Grid) -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5 mt-4">
         <div v-for="product in products" :key="product.id" class="glass-panel rounded-3xl overflow-hidden border border-slate-700/50 flex flex-col group relative">
            
            <!-- Image Area -->
            <div class="h-44 bg-slate-900 relative overflow-hidden shrink-0">
               <img v-if="product.image_url" :src="product.image_url" class="w-full h-full object-cover opacity-80 group-hover:opacity-100 group-hover:scale-105 transition-all duration-500" />
               <div v-else class="w-full h-full flex items-center justify-center text-slate-700 bg-slate-800/50">
                   <svg class="w-12 h-12" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
               </div>
               
               <!-- Price Tag -->
               <div class="absolute top-3 right-3 bg-emerald-500/90 backdrop-blur-md text-white font-black text-sm px-3 py-1 rounded-full shadow-lg border border-emerald-400/50">
                 ${{ product.price }}
               </div>

               <!-- Quick Actions (Edit/Delete) overlayed on image top left -->
               <div class="absolute top-3 left-3 flex gap-2">
                 <button @click="openProductModal(product)" class="w-8 h-8 rounded-full bg-slate-900/60 backdrop-blur-md border border-slate-600/50 flex items-center justify-center text-white active:scale-95 transition-transform">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                 </button>
                 <button @click="deleteProduct(product.id)" class="w-8 h-8 rounded-full bg-red-500/20 backdrop-blur-md border border-red-500/30 flex items-center justify-center text-red-400 active:scale-95 transition-transform">
                    <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                 </button>
               </div>
            </div>
            
            <!-- Details Area -->
            <div class="p-5 flex-1 flex flex-col">
               <div class="flex items-center gap-2 mb-2">
                  <span class="text-[9px] font-bold uppercase tracking-widest text-indigo-400">
                    {{ getCategoryName(product.category_id) }}
                  </span>
               </div>
               <h3 class="font-bold text-white text-lg tracking-tight leading-snug mb-2">{{ product.title }}</h3>
               <p class="text-sm text-slate-400 line-clamp-2 leading-relaxed flex-grow">{{ product.description || 'No description provided.' }}</p>
               
               <div v-if="product.attachment_url" class="mt-4 pt-4 border-t border-slate-700/50">
                  <a :href="product.attachment_url" target="_blank" class="flex items-center justify-center gap-2 w-full bg-slate-800/80 rounded-xl py-2.5 text-xs font-bold text-blue-400 border border-slate-700/50 hover:bg-slate-700 transition-colors">
                     <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" /></svg>
                     Attached Document
                  </a>
               </div>
            </div>
         </div>
      </div>
    </div>

    <!-- Modals Overlay (Mobile Bottom Sheet Style) -->
    <transition name="fade">
      <div v-if="showProductModal || showCategoryModal" class="fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm px-0 sm:px-4 pb-0 sm:pb-4">
        
        <!-- PRODUCT MODAL -->
        <div v-if="showProductModal" class="w-full max-w-lg bg-onyx sm:rounded-3xl rounded-t-3xl border border-slate-800 shadow-2xl overflow-hidden max-h-[90vh] flex flex-col slide-up relative">
           
           <div class="p-5 border-b border-slate-800 flex justify-between items-center sticky top-0 bg-onyx/90 backdrop-blur-md z-10">
              <h2 class="text-lg font-bold text-white tracking-tight">{{ isEditing ? 'Edit Product' : 'New Product' }}</h2>
              <button @click="showProductModal = false" class="text-slate-500 hover:text-white p-1 rounded-full"><svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
           </div>
           
           <div class="p-5 overflow-y-auto space-y-5 scrollbar-none">
              <div class="space-y-1.5 mt-2">
                <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Product Title</label>
                <input v-model="currentProduct.title" type="text" placeholder="e.g. Enterprise License" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors" />
              </div>

              <div class="grid grid-cols-2 gap-4">
                 <div class="space-y-1.5">
                   <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Price ($)</label>
                   <div class="relative">
                      <span class="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500">$</span>
                      <input v-model="currentProduct.price" type="number" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl pl-8 pr-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors" />
                   </div>
                 </div>
                 <div class="space-y-1.5">
                   <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Category</label>
                   <select v-model="currentProduct.category_id" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors appearance-none">
                     <option :value="null">Uncategorized</option>
                     <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                   </select>
                 </div>
              </div>

              <div class="space-y-1.5">
                <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Description</label>
                <textarea v-model="currentProduct.description" rows="3" placeholder="Tell the AI what this is useful for..." class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors resize-none"></textarea>
              </div>

              <div class="space-y-1.5">
                <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Image URL (Optional)</label>
                <input v-model="currentProduct.image_url" type="text" placeholder="https://" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors" />
              </div>
              
              <div class="space-y-1.5">
                <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Document URL (Optional)</label>
                <input v-model="currentProduct.attachment_url" type="text" placeholder="https:// Link to PDF/Doc" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors" />
              </div>
           </div>

           <div class="p-5 border-t border-slate-800 bg-slate-900/50 pb-safe">
              <button @click="saveProduct" class="w-full bg-aurora-gradient text-white font-bold py-3.5 rounded-xl text-sm shadow-lg shadow-purple-500/20 active:scale-[0.98] transition-all">
                {{ isEditing ? 'Save Changes' : 'Add to Catalog' }}
              </button>
           </div>
        </div>

        <!-- CATEGORY MODAL -->
        <div v-if="showCategoryModal" class="w-full max-w-sm bg-onyx sm:rounded-3xl rounded-t-3xl border border-slate-800 shadow-2xl overflow-hidden flex flex-col slide-up relative">
           <div class="p-5 border-b border-slate-800 flex justify-between items-center">
              <h2 class="text-lg font-bold text-white tracking-tight">New Category</h2>
              <button @click="showCategoryModal = false" class="text-slate-500 hover:text-white p-1 rounded-full"><svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg></button>
           </div>
           
           <div class="p-5 space-y-5">
              <div class="space-y-1.5">
                <label class="text-[10px] uppercase tracking-widest font-bold text-slate-500 pl-1">Category Name</label>
                <input v-model="currentCategory.name" type="text" placeholder="e.g. Services, Hardware" class="w-full bg-slate-900 border border-slate-700/80 rounded-2xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors" />
              </div>
           </div>

           <div class="p-5 border-t border-slate-800 bg-slate-900/50 pb-safe">
               <button @click="saveCategory" class="w-full bg-white text-slate-900 font-bold py-3.5 rounded-xl text-sm shadow-lg active:scale-[0.98] transition-all">
                Create Category
              </button>
           </div>
        </div>

      </div>
    </transition>

  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;  
  overflow: hidden;
}

/* Hide scrollbar for category pills but keep scroll functionality */
.scrollbar-none::-webkit-scrollbar {
  display: none;
}
.scrollbar-none {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* Mobile Bottom sheet slide animation */
.slide-up {
  animation: slideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

.fade-enter-active, .fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
}
</style>
