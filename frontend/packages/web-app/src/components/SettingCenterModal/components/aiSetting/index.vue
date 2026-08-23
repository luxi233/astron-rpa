<script setup lang="ts">
import { Button, Form, Input, message } from 'ant-design-vue'
import { useTranslation } from 'i18next-vue'
import { onMounted, reactive, ref } from 'vue'

import type { AIConfig } from '@/api/aiSetting'
import { apiGetAIConfig, apiSaveAIConfig, apiTestAIConfig } from '@/api/aiSetting'

import Card from '../card.vue'

const { t } = useTranslation()

// 掩码值(含***)原样回传, 服务端识别后跳过不覆盖
const formState = reactive<AIConfig>({
  AICHAT_BASE_URL: '',
  AICHAT_API_KEY: '',
  DEFAULT_MODEL: '',
  SMART_MODEL: '',
  CUA_BASE_URL: '',
  CUA_API_KEY: '',
  CUA_MODEL: '',
})

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)

async function loadConfig() {
  loading.value = true
  try {
    const res = await apiGetAIConfig()
    Object.assign(formState, res.data)
  }
  catch (e) {
    console.error('load ai config failed', e)
  }
  finally {
    loading.value = false
  }
}

async function handleSave() {
  saving.value = true
  try {
    await apiSaveAIConfig({ ...formState })
    message.success(t('settingCenter.aiSetting.saveSuccess'))
    await loadConfig()
  }
  catch (e) {
    console.error('save ai config failed', e)
  }
  finally {
    saving.value = false
  }
}

async function handleTest() {
  testing.value = true
  try {
    const res = await apiTestAIConfig()
    if (res.data?.ok)
      message.success(t('settingCenter.aiSetting.testOk'))
    else
      message.error(res.data?.message || t('settingCenter.aiSetting.testFail'))
  }
  catch (e) {
    console.error('test ai config failed', e)
  }
  finally {
    testing.value = false
  }
}

onMounted(loadConfig)
</script>

<template>
  <div class="space-y-3">
    <Card
      :title="$t('settingCenter.aiSetting.llmTitle')"
      :description="$t('settingCenter.aiSetting.llmDesc')"
      class="px-[20px] py-[17px] !items-start"
    />
    <Form label-align="left" :colon="false" class="px-1">
      <div class="space-y-4">
        <div class="flex items-center">
          <span class="w-[140px] flex-none text-sm">{{ $t('settingCenter.aiSetting.baseUrl') }}</span>
          <Input
            v-model:value="formState.AICHAT_BASE_URL"
            class="flex-1"
            :placeholder="$t('settingCenter.aiSetting.baseUrlPlaceholder')"
            :disabled="loading"
          />
        </div>
        <div class="flex items-center">
          <span class="w-[140px] flex-none text-sm">{{ $t('settingCenter.aiSetting.apiKey') }}</span>
          <Input.Password
            v-model:value="formState.AICHAT_API_KEY"
            class="flex-1"
            :placeholder="$t('settingCenter.aiSetting.apiKeyPlaceholder')"
            :disabled="loading"
          />
        </div>
        <div class="flex items-center">
          <span class="w-[140px] flex-none text-sm">{{ $t('settingCenter.aiSetting.defaultModel') }}</span>
          <Input
            v-model:value="formState.DEFAULT_MODEL"
            class="flex-1"
            :placeholder="$t('settingCenter.aiSetting.modelPlaceholder')"
            :disabled="loading"
          />
        </div>
      </div>
    </Form>

    <Card
      :title="$t('settingCenter.aiSetting.smartTitle')"
      :description="$t('settingCenter.aiSetting.smartDesc')"
      class="px-[20px] py-[17px] !items-start"
    />
    <Form label-align="left" :colon="false" class="px-1">
      <div class="flex items-center">
        <span class="w-[140px] flex-none text-sm">{{ $t('settingCenter.aiSetting.smartModel') }}</span>
        <Input
          v-model:value="formState.SMART_MODEL"
          class="flex-1"
          :placeholder="$t('settingCenter.aiSetting.modelPlaceholder')"
          :disabled="loading"
        />
      </div>
    </Form>

    <Card
      :title="$t('settingCenter.aiSetting.cuaTitle')"
      :description="$t('settingCenter.aiSetting.cuaDesc')"
      class="px-[20px] py-[17px] !items-start"
    />
    <Form label-align="left" :colon="false" class="px-1">
      <div class="space-y-4">
        <div class="flex items-center">
          <span class="w-[140px] flex-none text-sm">{{ $t('settingCenter.aiSetting.baseUrl') }}</span>
          <Input
            v-model:value="formState.CUA_BASE_URL"
            class="flex-1"
            :placeholder="$t('settingCenter.aiSetting.baseUrlPlaceholder')"
            :disabled="loading"
          />
        </div>
        <div class="flex items-center">
          <span class="w-[140px] flex-none text-sm">{{ $t('settingCenter.aiSetting.apiKey') }}</span>
          <Input.Password
            v-model:value="formState.CUA_API_KEY"
            class="flex-1"
            :placeholder="$t('settingCenter.aiSetting.apiKeyPlaceholder')"
            :disabled="loading"
          />
        </div>
        <div class="flex items-center">
          <span class="w-[140px] flex-none text-sm">{{ $t('settingCenter.aiSetting.cuaModel') }}</span>
          <Input
            v-model:value="formState.CUA_MODEL"
            class="flex-1"
            :placeholder="$t('settingCenter.aiSetting.modelPlaceholder')"
            :disabled="loading"
          />
        </div>
      </div>
    </Form>

    <div class="flex items-center gap-3 pt-1">
      <Button :loading="saving" type="primary" @click="handleSave">
        {{ $t('settingCenter.aiSetting.save') }}
      </Button>
      <Button :loading="testing" @click="handleTest">
        {{ $t('settingCenter.aiSetting.test') }}
      </Button>
      <span class="text-xs text-[rgba(0,0,0,0.45)] dark:text-[rgba(255,255,255,0.45)]">
        {{ $t('settingCenter.aiSetting.hotReloadTip') }}
      </span>
    </div>
  </div>
</template>
