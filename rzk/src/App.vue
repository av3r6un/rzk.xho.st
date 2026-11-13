<template>
  <Navbar />
  <router-view/>
</template>

<script>
import Navbar from './components/ui/Navbar.vue';

export default {
  name: 'App',
  components: {
    Navbar,
  },
};
</script>

<style lang="scss">

</style>
