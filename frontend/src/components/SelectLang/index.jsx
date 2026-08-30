import './index.less'

import { Icon, Menu, Dropdown } from 'ant-design-vue'
import { i18nRender } from '@/locales'
import i18nMixin from '@/store/i18n-mixin'

const locales = [
  'en-US',
  'vi-VN'
]

const languageLabels = {
  'en-US': 'English',
  'vi-VN': 'Ti\u1ebfng Vi\u1ec7t'
}

const languageIcons = {
  'en-US': 'EN',
  'vi-VN': 'VI'
}

const languageShortLabels = {
  'en-US': 'EN',
  'vi-VN': 'VI'
}

const SelectLang = {
  props: {
    prefixCls: {
      type: String,
      default: 'ant-pro-drop-down'
    }
  },
  name: 'SelectLang',
  mixins: [i18nMixin],
  render () {
    const { prefixCls } = this
    const changeLang = ({ key }) => {
      this.setLang(key)
    }
    const handleKeydown = event => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        event.currentTarget.click()
      }
    }
    const langMenu = (
      <Menu class={['menu', 'ant-pro-header-menu']} selectedKeys={[this.currentLang]} onClick={changeLang}>
        {locales.map(locale => (
          <Menu.Item key={locale}>
            <span class="language-code" aria-label={languageLabels[locale]}>
              {languageIcons[locale]}
            </span>
            {languageLabels[locale]}
          </Menu.Item>
        ))}
      </Menu>
    )
    const currentLabel = languageShortLabels[this.currentLang] || 'Lang'
    const title = `${i18nRender('navBar.lang')} · ${languageLabels[this.currentLang] || currentLabel}`
    return (
      <Dropdown overlay={langMenu} placement="bottomRight" trigger={['click']}>
        <span class={[prefixCls, 'language-action']} title={title} aria-label={title} role="button" tabIndex="0" onKeydown={handleKeydown}>
          <Icon type="global" class="language-action-icon" />
          <span class="language-action-label">{currentLabel}</span>
        </span>
      </Dropdown>
    )
  }
}

export default SelectLang
