<script setup lang="ts">
import { ref } from "vue";

import HomePage from "@/components/HomePage.vue";
import LoginPage from "@/components/LoginPage.vue";

const isAuthenticated = ref(false);
</script>

<template>
    <link
        rel="stylesheet"
        type="text/css"
        href="https://unpkg.com/primevue/resources/themes/mdc-light-indigo/theme.css"
    >
    <link
        rel="stylesheet"
        type="text/css"
        href="//cdnjs.cloudflare.com/ajax/libs/font-awesome/4.6.3/css/font-awesome.min.css"
    >
    <component
        :is="isAuthenticated ? HomePage : LoginPage"
        v-model="isAuthenticated"
    />
</template>

<style>
body {
    margin: 0;
}
#app {
    height: 100vh;
}
</style>