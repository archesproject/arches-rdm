<script setup lang="ts">
import LetterCircle from "@/components/LetterCircle.vue";

import type { TreeNode } from "primevue/tree/Tree";

const props: { node: TreeNode } = defineProps(["node"]);
</script>

<template>
    <div class="detail-container">
        <span class="item-header">
            <LetterCircle :node="node"/>
            <h2>{{ node.label }}</h2>
            <span class="item-type">{{ node.iconLabel }}</span>
        </span>
    </div>
</template>


<style scoped>
.detail-container {
    margin: 1rem;
}
.item-header {
    display: inline-flex;
    align-items: center;
    gap: 1rem;
    margin: 0.5rem 0.5rem 0rem 0.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid;
    width: 80%;
}
h2 {
    font-size: 1rem;
    margin: 0;
}
.item-type {
    font-size: small;
    font-weight: 200;
}
</style>
