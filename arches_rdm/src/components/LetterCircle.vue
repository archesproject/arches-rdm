<script setup lang="ts">
import { computed } from "vue";

import type { TreeNode } from "primevue/tree/Tree";

const props: { node: TreeNode } = defineProps(["node"]);

const color = computed(() => {
    if (props.node.data.top_concepts) {
        return 'bisque';
    }
    return 'orchid';
});

const letter = computed(() => {
    if (props.node.data.top_concepts) {
        return 'S';
    }
    return 'C';
});
</script>

<template>
    <div class="circle">
        <span class="letter">{{ letter }}</span>
    </div>
</template>

<style scoped>
.circle {
    width: 1.25rem;
    height: 1.25rem;
    border-radius: 50%;
    background-color: v-bind("color");
    font-weight: 600;
    align-self: center;
    display: grid;
}

.letter {
    text-align: center;
    align-self: center;
}
</style>
