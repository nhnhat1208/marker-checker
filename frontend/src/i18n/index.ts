import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import HttpBackend from 'i18next-http-backend'

i18n
  .use(HttpBackend)
  .use(initReactI18next)
  .init({
    backend: {
      loadPath: '/locales/{{lng}}.json',
    },
    lng: (localStorage.getItem('ui-lang') as string) || 'vi',
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
  })

export default i18n
