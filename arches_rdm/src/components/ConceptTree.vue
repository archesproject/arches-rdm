<script setup lang="ts">
import { computed, ref } from "vue";

import { useGettext } from "vue3-gettext";

import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Dropdown from "primevue/dropdown";
import Tree from "primevue/tree";

import LetterCircle from "@/components/LetterCircle.vue";

import { bestLabel } from "@/utils";

import type { Ref } from "vue";
import type {
    TreeContext,
    TreeExpandedKeys,
    TreeNode,
    TreeSelectionKeys,
} from "primevue/tree/Tree";
import type { Concept, Language, Scheme } from "@/types";

// todo(jtw): get from server when implementing other languages
const ENGLISH: Language = {
    code: "en",
    default_direction: "ltr",
    id: 1,
    isdefault: true,
    name: 'English',
    scope: 'system',
};
const LANGUAGE_CHOICES = [ENGLISH];

const expandedKeys: Ref<TreeExpandedKeys> = ref({});
const selectionKeys: Ref<TreeSelectionKeys> = ref({});
const filterValue = ref("");
const schemes: Ref<Scheme[]> = ref([]);
const selectedLanguage: Ref<Language> = ref(ENGLISH);

const selectedNode: Ref<TreeNode> = defineModel({});
const focusedNode: Ref<TreeNode> = ref({});

const toast = useToast();
const { $gettext } = useGettext();

const lightGray = "#f4f4f4";
const ERROR = "error";
const SCHEME_LABEL = $gettext("Scheme");
// const GUIDE_LABEL = $gettext("Guide Item");
const CONCEPT_LABEL = $gettext("Concept");
const FOCUS = $gettext("Focus");
const UNFOCUS = $gettext("Unfocus");

import { DJANGO_HOST } from "@/main";

const onSelect = (node: TreeNode) => {
    selectedNode.value = node;
};

const highlightedLabel = (text: string) => {
    if (!filterValue.value) {
        return text;
    }
    const regex = new RegExp(`(${filterValue.value})`, "gi");
    return text.replace(regex, "<b>$1</b>");
};

const onNodeExpand = (node: TreeNode) => {
    node.children.forEach((child: TreeNode) => {
        const grandchildren = child.children;
        if ((node.children.length + grandchildren.length) < 7) {
            expandedKeys.value[child.key] = true;
        }
    });
};

function conceptAsNode(concept: Concept): TreeNode {
    const node = {
        key: concept.id,
        label: bestLabel(concept, 'en').value,
        children: concept.narrower.map(child => conceptAsNode(child)),
        data: concept,
        iconLabel: CONCEPT_LABEL,
    };
    const focalNodeIdx = node.children.findIndex(child => child.data.id === focusedNode.value.data?.id);
    if (focalNodeIdx > -1) {
        node.children = [node.children[focalNodeIdx]];
    }
    return node;
}

function schemeAsNode(scheme: Scheme): TreeNode {
    const node = {
        key: scheme.id,
        label: bestLabel(scheme, 'en').value,
        children: scheme.top_concepts.map(top => conceptAsNode(top)),
        data: scheme,
        iconLabel: SCHEME_LABEL,
    };
    const focalNodeIdx = node.children.findIndex(child => child.data.id === focusedNode.value.data?.id);
    if (focalNodeIdx > -1) {
        node.children = [node.children[focalNodeIdx]];
    }
    return node;
}

const conceptTree = computed(() => {
    const focalNodeIdx = schemes.value.findIndex(scheme => scheme.id === focusedNode.value.data?.id);
    if (focalNodeIdx > -1) {
        return [schemeAsNode(schemes.value[focalNodeIdx])];
    }
    return schemes.value.map((scheme: Scheme) => schemeAsNode(scheme));
});

const expandAll = () => {
    for (const node of conceptTree.value) {
        expandNode(node);
    }
    expandedKeys.value = { ...expandedKeys.value };
};

const collapseAll = () => {
    expandedKeys.value = {};
};

const expandNode = (node: TreeNode) => {
    if (node.children && node.children.length) {
        expandedKeys.value[node.key] = true;
        for (const child of node.children) {
            expandNode(child);
        }
    }
};

const iconForFocusToggle = (node: TreeNode) => {
    return (
        focusedNode.value.data?.id === node.data.id
        ? 'fa fa-search-minus'
        : 'fa fa-bullseye'
    );
};

const labelForFocusToggle = (node: TreeNode) => {
    return (
        focusedNode.value.data?.id === node.data.id
        ? UNFOCUS
        : FOCUS
    );
};

const toggleFocus = (node: TreeNode) => {
    if (focusedNode.value.data?.id === node.data.id) {
        focusedNode.value = {};
    } else {
        focusedNode.value = node;
    }
};

const fetchSchemes = async () => {
    let errorText;
    const url = new URL("concept_trees/", DJANGO_HOST);
    try {
        const response = await fetch(url, { credentials: "include" });
        if (!response.ok) {
            errorText = response.statusText;
            const body = await response.json();
            errorText = body.message;
            throw new Error();
        } else {
            await response.json().then((data) => {
                schemes.value = data.schemes;
            });
        }
    } catch {
        toast.add({
            severity: ERROR,
            summary: errorText || $gettext("Unable to fetch schemes"),
        });
    }
};

await fetchSchemes();
</script>

<template>
    <div class="controls">
        <Button
            class="control"
            type="button"
            icon="fa fa-plus"
            :label="$gettext('Expand')"
            @click="expandAll"
            :pt="{
                icon: { style: { color: 'black', fontSize: 'x-small' } },
                label: { style: { color: 'black', fontWeight: '200' } },
            }"
        />
        <Button
            class="control"
            type="button"
            icon="fa fa-minus"
            :label="$gettext('Collapse')"
            @click="collapseAll"
            :pt="{
                icon: { style: { color: 'black', fontSize: 'x-small' } },
                label: { style: { color: 'black', fontWeight: '200' } },
            }"
        />
        <Dropdown
            v-model="selectedLanguage"
            :options="LANGUAGE_CHOICES"
            option-label="name"
            :placeholder="$gettext('Language')"
            checkmark
            :highlight-on-select="false"
            :pt="{
                root: { class: 'control' },
                input: { style: { fontFamily: 'inherit', fontSize: 'small', textAlign: 'center', fontWeight: '200' } },
                itemLabel: { style: { fontSize: 'small' } },
            }"
        />
    </div>
    <Tree
        v-model:selectionKeys="selectionKeys"
        :value="conceptTree"
        :expanded-keys
        :filter="true"
        :filter-placeholder="$gettext('Search for a concept')"
        filter-mode="lenient"
        selection-mode="single"
        :pt="{
            root: { style: { flexGrow: 1, overflow: 'auto' } },
            input: { style: { height: '2rem', fontSize: '14px' } },
            container: { style: { fontSize: '14px' } },
            content: ({ context }): { context: TreeContext } => ({
                style: {
                    background: context.selected ? lightGray : '',
                    height: '2rem',
                },
                tabindex: '0',
            }),
            nodeicon: { style: { display: 'none' } },
            label: { style: { textWrap: 'nowrap', display: 'flex' } },
            hooks: {
                onBeforeUpdate() {
                    // Snoop on the filterValue, because if we wait to react
                    // to the emitted filter event, the templated rows will
                    // have already renderd.
                    filterValue = $el.ownerDocument.getElementsByClassName('p-tree-filter')[0].value;
                },
            },
        }"
        @node-expand="onNodeExpand"
        @nodeSelect="onSelect"
    >
        <template #default="slotProps">
            <LetterCircle :node="slotProps.node" />
            <span v-html="highlightedLabel(slotProps.node.label)"></span>
            <i
                v-tooltip="labelForFocusToggle(slotProps.node)"
                role="button"
                :class="iconForFocusToggle(slotProps.node)"
                :aria-label="labelForFocusToggle(slotProps.node)"
                tabindex="0"
                :style="{ alignSelf: 'center' }"
                @click="toggleFocus(slotProps.node)"
                @keyup.enter="toggleFocus(slotProps.node)"
            />
        </template>
    </Tree>
</template>

<style scoped>
.controls {
    display: flex;
    background: #f3fbfd;
    padding: 1rem;
    gap: 0.5rem;
}

.control {
    flex: 0.33;
    border: 0;
    background: lightgray;
    font-size: smaller;
}

.button {
    font-size: small;
    height: 4rem;
    margin: 0.5rem;
    justify-content: center;
    font-weight: 200;
    text-wrap: nowrap;
}

span {
    padding: 0.5rem;
}
</style>
