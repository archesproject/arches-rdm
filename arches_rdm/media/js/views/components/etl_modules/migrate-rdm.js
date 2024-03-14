define([
    'knockout',
    'knockout-mapping',
    'jquery',
    'uuid',
    'arches',
    'viewmodels/alert',
    'viewmodels/alert-json',
    'templates/views/components/etl_modules/migrate-rdm.htm',
], function(ko, koMapping, $, uuid, arches, AlertViewModel, JsonErrorAlertViewModel, migrateRDMTemplate) {
    const viewModel = function(params) {
        const self = this;

        this.loadDetails = params.load_details;
        this.state = params.state;
        this.loading = params.loading || ko.observable();
        this.alert = params.alert;
        this.moduleId = params.etlmoduleid;
        this.loadId = params.loadId || uuid.generate();
        this.formData = new window.FormData();
        this.graphs = ko.observable();
        this.selectedLoadEvent = params.selectedLoadEvent || ko.observable();
        this.formatTime = params.formatTime;
        this.timeDifference = params.timeDifference;
        this.activeTab = params.activeTab || ko.observable();
        this.editHistoryUrl = `${arches.urls.edit_history}?transactionid=${ko.unwrap(params.selectedLoadEvent)?.loadid}`;
        
        self.runRDMMigration = function() {
            self.loading(true);            
            self.submit('start').then(data => {
                params.activeTab("import");
                self.formData.append('async', true);
                self.submit('write').then(data => {
                    console.log(data.results);
                }).fail(function(err) {
                    console.log(err);
                    self.alert(
                        new JsonErrorAlertViewModel(
                            'ep-alert-red',
                            err.responseJSON["data"],
                            null,
                            function(){}
                        )
                    )
                }).always(() => {
                    self.loading(false);
                });
            }).fail(error => console.log(error.responseJSON.data));
        };

        this.submit = function(action) {
            self.formData.append('action', action);
            self.formData.append('loadid', self.loadId);
            self.formData.append('module', self.moduleId);
            return $.ajax({
                type: "POST",
                url: arches.urls.etl_manager,
                data: self.formData,
                cache: false,
                processData: false,
                contentType: false,
            });
        };
    };
    ko.components.register('migrate-rdm', {
        viewModel: viewModel,
        template: migrateRDMTemplate,
    });
    return viewModel;
}); 