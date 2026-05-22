import { createApp } from 'vue'

import App from './App.vue'
import router from './router'
import './style.css'
import { installGlobalErrorHandler } from './utils/errorHandler'

const app = createApp(App)
app.use(router)
installGlobalErrorHandler(app)
app.mount('#app')
