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
  catch (reason) { error.value = reason instanceof Error ? reason.message : 'Agent 配置加载失败' }
  finally { loading.value = false }
})
</script>

<template>
  <div class="studio-page">
    <header class="studio-page-header">
      <div><span class="studio-eyebrow">AGENT CAPABILITIES</span><h1>Agent 配置</h1><p>查看当前智能体模型、检索能力与可调用业务工具</p></div>
      <span class="readonly-badge"><AppIcon name="shield" />只读模式</span>
    </header>
    <div v-if="error" class="studio-alert error"><AppIcon name="warning" />{{ error }}</div>
    <div v-if="loading" class="studio-loading">正在读取 Agent 配置…</div>

    <template v-if="config">
      <section class="agent-profile-card">
        <span class="agent-profile-icon"><AppIcon name="bot" /></span>
        <div><small>当前智能体</small><h2>{{ config.agent_name }}</h2><p>面向社会治理事件查询、趋势研判、风险识别和知识辅助的业务 Agent</p></div>
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
        <div class="studio-panel-header"><div><h2>业务工具</h2><p>Agent 可根据问题动态选择以下工具；本页面不提供在线开关</p></div><span class="studio-count">{{ config.tools.length }} 个已启用</span></div>
        <div class="tool-grid"><article v-for="tool in config.tools" :key="tool.name"><span><AppIcon name="action" /></span><div><strong>{{ tool.name }}</strong><p>{{ tool.description }}</p></div><i title="已启用" /></article></div>
      </section>

      <div class="readonly-note"><AppIcon name="shield" /><div><strong>为什么当前不开放编辑？</strong><p>比赛演示期间，模型、Prompt 与工具配置保持只读，避免误操作影响现场闭环。密钥只通过本机环境变量配置，接口不会返回密钥内容。</p></div></div>
    </template>
  </div>
</template>
