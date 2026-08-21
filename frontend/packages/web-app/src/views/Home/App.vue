<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterView } from 'vue-router'

import BackendReaction from '@/components/BackendReaction/Index.vue'
import ConfigProvider from '@/components/ConfigProvider/index.vue'
import GlobalRegister from '@/components/GlobalRegister/Index.vue'
import Loading from '@/components/Loading.vue'
import { useAppConfigStore } from '@/stores/useAppConfig'
import { usePickStore } from '@/stores/usePickStore'
import LiveControlTree from '@/views/Arrange/components/pick/LiveControlTree.vue'

const appStore = useAppConfigStore()
const usePick = usePickStore()
// 深度捕获进行中: 主窗口已收缩为右侧面板, 根布局整屏承载实时控件树
const isDeepPicking = computed(() => usePick.isDeepPicking)

onMounted(() => appStore.checkUpdate())
</script>

<template>
  <ConfigProvider>
    <BackendReaction />
    <LiveControlTree v-if="isDeepPicking" />
    <RouterView v-else />
    <Loading />
    <GlobalRegister />
  </ConfigProvider>
</template>
