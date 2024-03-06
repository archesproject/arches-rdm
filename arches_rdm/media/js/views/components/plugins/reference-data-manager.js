import ko from 'knockout';
// import RDMVueApplication from '@/components/App.vue';
import createVueApplication from 'utils/create-vue-application';
import RDMAppTemplate from 'templates/views/components/plugins/reference-data-manager.htm';

import packageJSON from 'arches_rdm/package.json'


ko.components.register('reference-data-manager', {
    viewModel: function() {
        // createVueApplication(packageJSON.name, RDMVueApplication).then(vueApp => {
        //     vueApp.mount('#rdm-mounting-point');
        // });
    },
    template: RDMAppTemplate,
});