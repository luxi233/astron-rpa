<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'

import BackendReaction from '@/components/BackendReaction/Index.vue'
import ConfigProvider from '@/components/ConfigProvider/index.vue'
import GlobalRegister from '@/components/GlobalRegister/Index.vue'
import Loading from '@/components/Loading.vue'
import { useAppConfigStore } from '@/stores/useAppConfig'

const appStore = useAppConfigStore()
// 深度捕获的实时控件树已改为独立面板窗口(见 views/DeepPick), 根布局不再替换卸载 RouterView,
// 避免拾取进行中 Arrange 被卸载触发 stopPickServices 误杀拾取三件套

onMounted(() => appStore.checkUpdate())
</script>

<template>
  <ConfigProvider>
    <BackendReaction />
    <RouterView />
    <Loading />
    <GlobalRegister />
  </ConfigProvider>
</template>
