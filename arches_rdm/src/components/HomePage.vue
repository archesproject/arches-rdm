<script setup lang="ts">
import { ref } from "vue";
import { useGettext } from "vue3-gettext";

import Button from "primevue/button";
import ProgressSpinner from "primevue/progressspinner";
import Splitter from "primevue/splitter";
import SplitterPanel from "primevue/splitterpanel";

import ConceptTree from "@/components/ConceptTree.vue";
import DetailPane from "@/components/DetailPane.vue";

import type { TreeNode } from "primevue/tree/Tree";

const { $gettext } = useGettext();

const selectedNode: Ref<TreeNode> = ref({});
const isAuthenticated = defineModel();

const signOut = () => {
    // TODO(jtw): implement
    isAuthenticated.value = false;
};
</script>

<template>
    <main>
        <div class="header">
            <h1>{{ $gettext('LINGO') }}</h1>
            <Button @click="signOut">
                {{ $gettext('Sign out') }}
            </Button>
        </div>
        <Splitter>
            <SplitterPanel
                :size="45"
                :min-size="20"
            >
                <Suspense>
                    <ConceptTree v-model="selectedNode" />
                    <template #fallback>
                        <ProgressSpinner style="display: flex" />
                    </template>
                </Suspense>
            </SplitterPanel>
            <SplitterPanel
                :size="55"
                :min-size="20"
            >
                <DetailPane v-if="Object.keys(selectedNode).length" :node="selectedNode" />
            </SplitterPanel>
        </Splitter>
    </main>
</template>

<style scoped>
main {
    height: 100%;
    display: flex;
    flex-direction: column;
}

.header {
    display: flex;
    justify-content: space-between;
    background: linear-gradient(to right, #3F51B5, gray);
}

.header button {
    color: black;
    background: #f4f4f4;
    height: 2rem;
    align-self: center;
    margin-right: 0.5rem;
}

h1 {
    font-size: 1rem;
    padding: 1rem;
    margin: 0;
    color: white;
}

.p-splitter {
    border: 0;
    flex-grow: 1;
    overflow: hidden;
}

.p-splitter-panel {
    display: flex;
    flex-direction: column;
}
</style>
