import { createApp } from 'vue';
import { createGettext } from 'vue3-gettext';

import PrimeVue from 'primevue/config';
import ConfirmationService from 'primevue/confirmationservice';
import DialogService from 'primevue/dialogservice';
import ToastService from 'primevue/toastservice';
import Tooltip from 'primevue/tooltip';

import LingoApp from '@/App.vue';

export const DJANGO_HOST = new URL('http://localhost:8029/');


document.title = 'Lingo - Vocabulary Management';

fetch(new URL('/api/get_frontend_i18n_data', DJANGO_HOST)).then(resp => {
    if (!resp.ok) {
        throw new Error(resp.statusText);
    }
    return resp.json();
}).then(respJSON => {
    const gettext = createGettext({
        availableLanguages: respJSON['enabled_languages'],
        defaultLanguage: respJSON['language'],
        translations: respJSON['translations'],
    });

    createApp(LingoApp)
        .use(PrimeVue)
        .use(gettext)
        .use(ConfirmationService)
        .use(DialogService)
        .use(ToastService)
        .directive('tooltip', Tooltip)
        .mount('#app');
});
