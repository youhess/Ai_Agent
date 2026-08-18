<script setup lang="ts">
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, GraphicComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { init, use, type ECharts } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps<{ option: EChartsOption }>()
const chartEl = ref<HTMLDivElement>()
use([LineChart, PieChart, GridComponent, GraphicComponent, LegendComponent, TooltipComponent, CanvasRenderer])

let chart: ECharts | undefined
let observer: ResizeObserver | undefined

onMounted(() => {
  if (!chartEl.value) return
  chart = init(chartEl.value)
  chart.setOption(props.option)
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(chartEl.value)
})

watch(() => props.option, (option) => chart?.setOption(option, true), { deep: true })

onBeforeUnmount(() => {
  observer?.disconnect()
  chart?.dispose()
})
</script>

<template><div ref="chartEl" class="chart-canvas" /></template>
