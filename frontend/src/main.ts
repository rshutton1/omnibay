import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import './styles/main.css'

const app = createApp(App)

// Last resort: anything the in-app boundary does not catch still gets logged
// rather than vanishing silently.
app.config.errorHandler = (error, _instance, info) => {
  console.error('[omnibay] unhandled error', info, error)
}

app.use(createPinia()).use(router).mount('#app')
