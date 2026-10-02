// Math is emitted as native MathML at build time; no math webfonts load.
// Type comes from the SZL KANCHAY system font stacks (public/szl/
// szl-design-system.css), so extend the default theme without its bundled webfont.
import DefaultTheme from 'vitepress/theme-without-fonts'
import './custom.css'

export default {
  extends: DefaultTheme
}
