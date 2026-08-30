<template>
  <nav class="datavest-top-menu" aria-label="Primary navigation">
    <router-link
      v-for="item in directItems"
      :key="item.path"
      class="datavest-top-menu__item"
      :class="{ 'is-active': selectedKey === item.path }"
      :to="routeTarget(item)"
      :aria-current="selectedKey === item.path ? 'page' : null"
    >
      <a-icon v-if="item.meta && item.meta.icon" :type="item.meta.icon" />
      <span>{{ menuTitle(item) }}</span>
    </router-link>

    <a-dropdown
      v-for="item in groupedItems"
      :key="item.path"
      placement="bottomLeft"
      :trigger="['hover', 'click']"
      overlay-class-name="datavest-top-menu-dropdown"
    >
      <button
        type="button"
        class="datavest-top-menu__item datavest-top-menu__item--group"
        :class="{ 'is-active': selectedKey === item.path }"
        :aria-expanded="String(selectedKey === item.path)"
        aria-haspopup="menu"
      >
        <a-icon v-if="item.meta && item.meta.icon" :type="item.meta.icon" />
        <span>{{ menuTitle(item) }}</span>
        <a-icon type="down" class="datavest-top-menu__arrow" />
      </button>
      <a-menu slot="overlay" :selected-keys="[selectedChildKey(item)]">
        <a-menu-item v-for="child in item.children || []" :key="child.path">
          <router-link :to="routeTarget(child)">
            <a-icon v-if="child.meta && child.meta.icon" :type="child.meta.icon" />
            <span>{{ menuTitle(child) }}</span>
          </router-link>
        </a-menu-item>
      </a-menu>
    </a-dropdown>
  </nav>
</template>

<script>
export default {
  name: 'TopMenu',
  props: {
    menus: { type: Array, default: () => [] },
    selectedKey: { type: String, default: '' },
    currentPath: { type: String, default: '' },
    i18nRender: { type: Function, default: null }
  },
  computed: {
    directItems () {
      return this.menus.filter(item => !(item && item.children && item.children.length))
    },
    groupedItems () {
      return this.menus.filter(item => item && item.children && item.children.length)
    }
  },
  methods: {
    menuTitle (item) {
      const title = item && item.meta && item.meta.title
      return title && this.i18nRender ? this.i18nRender(title) : (title || (item && item.name) || '')
    },
    routeTarget (item) {
      return item && item.name ? { name: item.name } : { path: item && item.path }
    },
    selectedChildKey (item) {
      const child = (item && item.children || []).find(route => {
        const path = route && route.path
        return path && (this.currentPath === path || this.currentPath.indexOf(`${path}/`) === 0)
      })
      return child ? child.path : ''
    }
  }
}
</script>

<style lang="less">
.datavest-top-menu {
  display: flex;
  align-items: center;
  flex: 1 1 auto;
  gap: 6px;
  min-width: 0;
  height: 64px;
  overflow: visible;
  white-space: nowrap;
}

.datavest-top-menu__item {
  display: inline-flex;
  align-items: center;
  flex: 0 1 auto;
  gap: 7px;
  min-width: 0;
  height: 38px;
  margin: 0;
  padding: 0 13px;
  border: 1px solid transparent;
  border-radius: 10px;
  color: var(--header-nav-ink, rgba(15, 23, 42, .74));
  background: transparent;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: -.01em;
  line-height: 36px;
  text-decoration: none;
  cursor: pointer;
  transition: transform 180ms ease, background-color 180ms ease, border-color 180ms ease, box-shadow 180ms ease, color 180ms ease;
}

.datavest-top-menu__item:hover {
  transform: translateY(-1px);
  border-color: var(--header-nav-border, rgba(37, 99, 235, .18));
  background: var(--header-nav-hover, rgba(37, 99, 235, .07));
  box-shadow: 0 4px 12px var(--header-nav-shadow, rgba(15, 23, 42, .08));
  color: var(--primary-color, #2563eb);
}

.datavest-top-menu__item.is-active {
  border-color: var(--header-nav-border-active, rgba(37, 99, 235, .30));
  background: var(--header-nav-active, rgba(37, 99, 235, .13));
  color: var(--primary-color, #2563eb);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, .12), 0 4px 14px var(--header-nav-shadow, rgba(15, 23, 42, .08));
}

.datavest-top-menu__item:active {
  transform: translateY(1px) scale(.985);
  box-shadow: none;
}

.datavest-top-menu__item:focus-visible {
  outline: 2px solid var(--primary-color, #2563eb);
  outline-offset: 2px;
}

.datavest-top-menu__item > .anticon { flex: 0 0 auto; }
.datavest-top-menu__arrow { transition: transform 180ms ease; }
.ant-dropdown-open .datavest-top-menu__arrow { transform: rotate(180deg); }

.datavest-top-menu-dropdown {
  .ant-dropdown-menu {
    min-width: 210px;
    padding: 7px;
    border: 1px solid var(--header-nav-border, rgba(37, 99, 235, .18));
    border-radius: 11px;
    box-shadow: 0 14px 30px var(--header-nav-shadow, rgba(15, 23, 42, .14));
  }

  .ant-dropdown-menu-item {
    min-height: 38px;
    margin: 2px 0;
    padding: 0 10px;
    border-radius: 8px;
    line-height: 38px;
  }

  .ant-dropdown-menu-item:hover,
  .ant-dropdown-menu-item-active,
  .ant-dropdown-menu-item-selected {
    background: var(--header-nav-hover, rgba(37, 99, 235, .07));
    color: var(--primary-color, #2563eb);
  }

  .ant-dropdown-menu-item > a {
    display: flex;
    align-items: center;
    gap: 8px;
    color: inherit;
    line-height: 38px;
    text-decoration: none;
  }
}

@media (max-width: 1366px) and (min-width: 769px) {
  .datavest-top-menu { gap: 4px; }
  .datavest-top-menu__item { padding: 0 9px; font-size: 11px; }
}

@media (max-width: 900px) and (min-width: 769px) {
  .datavest-top-menu__item { gap: 5px; padding: 0 6px; font-size: 10px; }
}

body.dark .datavest-top-menu__item,
body.realdark .datavest-top-menu__item { color: var(--header-nav-ink, rgba(248, 250, 252, .82)); }

body.dark .datavest-top-menu__item:hover,
body.realdark .datavest-top-menu__item:hover,
body.dark .datavest-top-menu__item.is-active,
body.realdark .datavest-top-menu__item.is-active { color: var(--primary-color, #2563eb); }
</style>
