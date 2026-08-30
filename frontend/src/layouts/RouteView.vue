<script lang="jsx">
export default {
  name: 'RouteView',
  props: {
    keepAlive: {
      type: Boolean,
      default: true
    }
  },
  data () {
    return {}
  },
  render () {
    const { $route } = this
    const routeKey = $route.fullPath || $route.path
    return <router-view key={routeKey} />
  }
}
</script>
