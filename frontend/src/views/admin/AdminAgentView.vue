<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppIcon from '../../components/AppIcon.vue'
import { getAgentConfig } from '../../api'
import type { AgentConfig } from '../../types'

const config = ref<AgentConfig | null>(null)
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try { config.value = await getAgentConfig() }
  catch (reason) { error.value = reason instanceof Error ? reason.message : '智能分析配置加载失败' }
  finally { loading.value = false }
})
</script>

<template>
  <div class="studio-page">
    <header class="studio-page-header">
      <div><span class="studio-section-label">平台管理中心</span><h1>智能分析配置</h1><p>查看当前分析模型、知识检索方式与业务能力</p></div>
      <span class="readonly-badge"><AppIcon name="shield" />只读模式</span>
    </header>
    <div v-if="error" class="studio-alert error"><AppIcon name="warning" />{{ error }}</div>
    <div v-if="loading" class="studio-loading">正在读取智能分析配置…</div>

    <template v-if="config">
      <section class="agent-profile-card">
        <span class="agent-profile-icon"><AppIcon name="bot" /></span>
        <div><small>当前分析助手</small><h2>{{ config.agent_name }}</h2><p>用于社会治理事件查询、趋势研判、风险识别和政策资料辅助</p></div>
        <span class="studio-status indexed">运行配置已加载</span>
      </section>

      <section class="config-grid">
        <article class="studio-panel config-card"><div class="config-card-title"><AppIcon name="spark" /><div><h2>模型服务</h2><p>回答生成与自然语言理解</p></div></div>
          <dl><div><dt>Provider</dt><dd>{{ config.provider }}</dd></div><div><dt>模型</dt><dd>{{ config.model }}</dd></div><div><dt>Temperature</dt><dd>{{ config.temperature }}</dd></div><div><dt>服务状态</dt><dd><span class="studio-status" :class="config.llm_configured ? 'indexed' : 'pending'">{{ config.llm_configured ? '密钥已配置' : '本地兜底模式' }}</span></dd></div></dl>
        </article>
        <article class="studio-panel config-card"><div class="config-card-title"><AppIcon name="document" /><div><h2>知识检索</h2><p>资料召回与回答溯源</p></div></div>
          <dl><div><dt>检索模式</dt><dd>{{ config.retrieval_mode === 'hybrid' ? '混合检索' : '关键词兜底' }}</dd></div><div><dt>Embedding</dt><dd><span class="studio-status" :class="config.embedding_configured ? 'indexed' : 'pending'">{{ config.embedding_configured ? '服务已配置' : '未配置' }}</span></dd></div><div><dt>语义权重</dt><dd>{{ config.retrieval_mode === 'hybrid' ? '70%' : '-' }}</dd></div><div><dt>关键词权重</dt><dd>{{ config.retrieval_mode === 'hybrid' ? '30%' : '100%' }}</dd></div></dl>
        </article>
      </section>

      <section class="studio-panel">
        <div class="studio-panel-header"><div><h2>业务能力</h2><p>系统可根据问题自动调用以下分析能力，本页面不提供在线开关</p></div><span class="studio-count">{{ config.tools.length }} 项已启用</span></div>
        <div class="tool-grid"><article v-for="tool in config.tools" :key="tool.name"><span><AppIcon name="action" /></span><div><strong>{{ tool.description }}</strong><p>{{ tool.name }}</p></div><i title="已启用" /></article></div>
      </section>

      <div class="readonly-note"><AppIcon name="shield" /><div><strong>配置安全说明</strong><p>演示期间模型、提示规则与业务能力保持只读，避免误操作影响系统运行。服务密钥仅通过本机环境变量配置，页面和接口均不会返回密钥内容。</p></div></div>
    </template>
  </div>
</template>
