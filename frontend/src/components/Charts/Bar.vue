<template>
  <div :style="{ padding: '0 0 32px 32px' }">
    <h4 :style="{ marginBottom: '20px' }">{{ title }}</h4>
    <v-chart
      height="254"
      :data="data"
      :forceFit="true"
      :scale="chartScale"
      :padding="['auto', 'auto', '40', '50']">
      <v-tooltip />
      <v-axis />
      <v-bar position="x*y"/>
    </v-chart>
  </div>
</template>

<script>
export default {
  name: 'Bar',
  props: {
    title: {
      type: String,
      default: ''
    },
    data: {
      type: Array,
      default: () => {
        return []
      }
    },
    scale: {
      type: Array,
      default: () => {
        return [{
          dataKey: 'x',
          min: 2
        }, {
          dataKey: 'y',
          min: 1,
          max: 22
        }]
      }
    },
    tooltip: {
      type: Array,
      default: () => {
        return [
          'x*y',
          (x, y) => ({
            name: x,
            value: y
          })
        ]
      }
    }
  },
  data () {
    return {
    }
  },
  computed: {
    chartScale () {
      return this.scale.map(item => item.dataKey === 'y'
        ? { ...item, title: this.$t('common.time'), alias: this.$t('common.time') }
        : item)
    }
  }
}
</script>
