<script setup lang="ts">
import { computed, ref } from "vue";

import { useGettext } from "vue3-gettext";

import { useToast } from "primevue/usetoast";
import Button from "primevue/button";
import Dropdown from "primevue/dropdown";
import Tree from "primevue/tree";

import LetterCircle from "@/components/LetterCircle.vue";

import { bestLabel } from "@/utils.ts";

import type { Ref } from "vue";
import type {
    TreeContext,
    TreeExpandedKeys,
    TreeNode,
    TreeSelectionKeys,
} from "primevue/tree/Tree";
import type { Concept, Labellable, Language, NodeAndParentInstruction, Scheme } from "@/types";

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

const conceptAsNodeAndParentInstruction = (concept: Concept) : NodeAndParentInstruction => {
    return conceptOrSchemeAsNodeAndParentInstruction(concept, concept.narrower);
};

const schemeAsNodeAndParentInstruction = (scheme: Scheme) : NodeAndParentInstruction => {
    return conceptOrSchemeAsNodeAndParentInstruction(scheme, scheme.top_concepts);
};

const conceptOrSchemeAsNodeAndParentInstruction = (
    labellable: Labellable, children: Concept[]
) : NodeAndParentInstruction => {
    let childrenAsNodes: TreeNode[];
    const nodesAndInstructions = children.map(child => conceptAsNodeAndParentInstruction(child));
    const parentOfFocusedNode = nodesAndInstructions.find(obj => obj.parentShouldHideSiblings);
    if (parentOfFocusedNode) {
        childrenAsNodes = [parentOfFocusedNode.node];
    } else {
        childrenAsNodes = nodesAndInstructions.map(obj => obj.node);
    }
    const iconLabel = (labellable as Scheme).top_concepts ? SCHEME_LABEL : CONCEPT_LABEL;

    const node: TreeNode = {
        key: labellable.id,
        label: bestLabel(labellable, 'en').value,
        children: childrenAsNodes,
        data: labellable,
        iconLabel,
    };

    let parentShouldHideSiblings = !!parentOfFocusedNode;
    if (!parentShouldHideSiblings) {
        const focalNodeIdx = node.children.findIndex(
            (child: TreeNode) => child.data.id === focusedNode.value.data?.id
        );
        if (focalNodeIdx > -1) {
            node.children = [node.children[focalNodeIdx]];
            parentShouldHideSiblings = true;
        }
    }

    return {node, parentShouldHideSiblings};
};

const conceptTree = computed(() => {
    const focalNodeIdx = schemes.value.findIndex(scheme => scheme.id === focusedNode.value.data?.id);
    if (focalNodeIdx > -1) {
        return [schemeAsNodeAndParentInstruction(schemes.value[focalNodeIdx]).node];
    }
    const nodesAndInstructions = schemes.value.map((scheme: Scheme) => schemeAsNodeAndParentInstruction(scheme));
    const parentOfFocusedNode = nodesAndInstructions.find(obj => obj.parentShouldHideSiblings);
    if (parentOfFocusedNode) {
        return [parentOfFocusedNode.node];
    }
    return nodesAndInstructions.map(obj => obj.node);
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
    try {
        const response = await fetch("/concept_trees/", { credentials: "include" });
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
        :filter-placeholder="$gettext('Filter concept hierarchies')"
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
                    // have already rendered.
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
