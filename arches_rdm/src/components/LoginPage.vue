<script setup lang="ts">
import { ref } from "vue";
import { useGettext } from "vue3-gettext";
import Cookies from "js-cookie";

import InputText from "primevue/inputtext";
import Button from "primevue/button";

import { DJANGO_HOST } from "@/main.ts";

const { $gettext } = useGettext();

const isAuthenticated = defineModel();
const username = ref();
const password = ref();

const setCsrfToken = async () => {
    await fetch(new URL("/csrf/", DJANGO_HOST)).then(
        async (response) => {
            const data = await response.json();
            Cookies.set("csrftoken", data.csrftoken);
        }
    );
};

const submit = async () => {
    if (!Cookies.get("csrftoken")) {
        await setCsrfToken();
    }

    const url = new URL("/login/", DJANGO_HOST);
    const requestOptions = {
        method: "POST",
        credentials: "include",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": Cookies.get("csrftoken"),
        },
        body: JSON.stringify({
            username: username.value,
            password: password.value,
        }),
    };

    let errorText;
    try {
        const response = await fetch(url, requestOptions);
        if (response.ok) {
            // const data = await response.json();
            isAuthenticated.value = true;
            await setCsrfToken();
        } else {
            errorText = response.statusText;
            const data = await response.json();
            errorText = data.message;
            throw new Error();
        }
    } catch {
        alert(errorText);
    }
};
</script>

<template>
    <form>
        <h1>{{ $gettext('LINGO') }}</h1>
        <h2>{{ $gettext('Vocabulary management powered by Arches.') }}</h2>
        <InputText
            v-model="username"
            :placeholder="$gettext('Username')"
            aria-label="$gettext('Username')"
            autocomplete="username"
        />
        <InputText
            v-model="password"
            :placeholder="$gettext('Password')"
            aria-label="$gettext('Password')"
            type="password"
            autocomplete="password"
        />

        <Button
            type="button"
            :label="$gettext('Sign in')"
            @click="submit"
        />
    </form>
</template>

<style scoped>
form {
    position: absolute;
    left: 5%;
    display: flex;
    flex-direction: column;
    gap: 1rem;
    width: 30%;
}

input {
    width: 100%;
}
</style>
