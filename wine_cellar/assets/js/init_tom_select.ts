import TomSelect from 'tom-select'
import { TomSettings } from 'tom-select/dist/esm/types/settings.js';
import { RecursivePartial, TomCreateCallback} from 'tom-select/dist/esm/types/core.js';


function initTomSelect (): void {
  document.querySelectorAll('select').forEach((el) => {
    const rawConfig : string | undefined = el.dataset.tom_config
    const clear : boolean = Boolean(JSON.parse(el.dataset.clear ?? "false"))
    const clearOpts : boolean = Boolean(JSON.parse(el.dataset.clearOpts ?? "false"))
    const enableSearch : boolean = Boolean(JSON.parse(el.dataset.search ?? "false"))
    let config : RecursivePartial<TomSettings> = {
      create: false,
      closeAfterSelect: true,
      maxItems: 1,
      // disable search by default
      controlInput: '',
      allowEmptyOption: true,
    }
    if (rawConfig) {
      config = JSON.parse(rawConfig)
      if (config.create) {
        config.create = function (input:string,create:TomCreateCallback) : boolean  {
          create({value: 'tom_new_opt' + input, text: input })
          return true
        }
        // Enable search if create is true, so users can type
        delete config.controlInput
      }
    }
    // Enable search if data-search="true" is set
    if (enableSearch) {
      delete config.controlInput
    }
    const ts = new TomSelect(el, config)
    if (clear) {
      ts.clear()
    }
    if (clearOpts) {
      ts.clearOptions()
    }
  })
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initTomSelect)
} else {
  initTomSelect()
}