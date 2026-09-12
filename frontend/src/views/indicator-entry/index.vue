<template>
  <indicator-ide v-if="authenticated" />
  <guest-indicator-chart v-else />
</template>

<script>
import { mapGetters } from 'vuex'
import storage from 'store'
import { ACCESS_TOKEN } from '@/store/mutation-types'
import { hasAccessToken } from '@/utils/guestAccess'
import IndicatorIde from '@/views/indicator-ide'
import GuestIndicatorChart from '@/views/indicator-guest'

export default {
  name: 'IndicatorEntry',
  components: { IndicatorIde, GuestIndicatorChart },
  computed: {
    ...mapGetters(['token']),
    authenticated () {
      return hasAccessToken(this.token || storage.get(ACCESS_TOKEN))
    }
  }
}
</script>
