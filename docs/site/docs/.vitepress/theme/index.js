// Fonts come from the vendored SZL Kanchay export (public/kanchay/kanchay.css,
// linked in config.mjs), so extend the default theme without its bundled Inter.
import DefaultTheme from 'vitepress/theme-without-fonts'
import './custom.css'

export default {
  extends: DefaultTheme
}
